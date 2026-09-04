"""
Deteccao de EPI (colete refletivo e capacete) sobre YOLOv8-pose.

A pose nao serve so para desenhar o esqueleto: os keypoints delimitam
onde cada EPI deve estar. Sem isso a analise de cor cai em regioes
erradas. Em teste, o recorte fixo por percentual da caixa acabava
medindo o piso do galpao em pessoas de perfil.

Estrategia por peca:

  colete    ombros (kp 5,6) ate a bacia (kp 11,12), cobertura HSV de
            laranja/amarelo refletivo.

  capacete  topo do cranio ate o meio da cabeca. Nao basta casar cor:
            capacete varia muito (laranja, amarelo, branco, azul). O que
            discrimina e a combinacao de superficie lisa, cor nao-pele e
            nao-cabelo, dentro de uma mascara eliptica ajustada a cabeca.
            Medir num retangulo fazia o teto claro do galpao entrar na
            conta e gerar falso positivo em cabeca descoberta.

A escala vertical da cabeca vem da distancia topo-da-caixa -> ombro,
medida direta. Deriva-la da largura da cabeca era indireto e colapsava
o recorte para poucos pixels de altura quando a estimativa errava.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from ultralytics import YOLO

import config

# indices de keypoint COCO-17
NOSE, EYE_L, EYE_R, EAR_L, EAR_R = 0, 1, 2, 3, 4
SHOULDER_L, SHOULDER_R = 5, 6
HIP_L, HIP_R = 11, 12

# Colete laranja/amarelo refletivo sob luz fluorescente de galpao. A faixa e
# larga porque o material refletivo estoura a saturacao de forma irregular.
VEST_HSV = (
    ((0, 80, 70), (20, 255, 255)),
    ((0, 50, 70), (12, 255, 255)),
    ((14, 70, 70), (32, 255, 255)),
    ((160, 80, 70), (180, 255, 255)),
)

# Matizes de capacete industrial: laranja, amarelo, verde, azul e vermelho
# (o vermelho envolve o zero do canal H, dai as duas pontas).
HELMET_HUES = ((3, 32), (25, 42), (45, 88), (92, 132), (0, 7), (172, 180))


@dataclass
class Detection:
    """Uma pessoa detectada e o veredito de cada EPI."""

    box: tuple[int, int, int, int]
    keypoints: list[tuple[float, float, float]] | None = None
    confidence: float = 0.0

    has_vest: bool = False
    has_helmet: bool = False
    vest_score: float = 0.0
    helmet_score: float = 0.0

    vest_roi: tuple[int, int, int, int] | None = None
    helmet_roi: tuple[int, int, int, int] | None = None

    track_id: int = -1
    violation_frames: int = 0
    zones: list[str] = field(default_factory=list)

    @property
    def compliant(self) -> bool:
        """Conformidade exige as duas pecas."""
        return self.has_vest and self.has_helmet


def keypoint(kps, index: int, min_conf: float | None = None):
    """Devolve (x, y) do keypoint se ele for confiavel, senao None.

    O YOLO preenche keypoints ocultos com (0, 0) e confianca baixa;
    usa-los sem filtrar desloca os recortes de analise.
    """
    if kps is None or index >= len(kps):
        return None
    x, y, conf = kps[index]
    if conf < (config.KEYPOINT_MIN_CONF if min_conf is None else min_conf):
        return None
    if x <= 0 and y <= 0:
        return None
    return int(x), int(y)


def face_center(kps):
    """Centro dos keypoints faciais, usado para identificar a pessoa."""
    pts = [p for p in (keypoint(kps, i)
                       for i in (NOSE, EYE_L, EYE_R, EAR_L, EAR_R)) if p]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts))


def vest_roi(box, kps, frame_w: int, frame_h: int):
    """Faixa do tronco onde o colete deve aparecer: ombros ate a bacia."""
    x1, y1, x2, y2 = box
    height = y2 - y1

    sl, sr = keypoint(kps, SHOULDER_L), keypoint(kps, SHOULDER_R)
    hl, hr = keypoint(kps, HIP_L), keypoint(kps, HIP_R)

    if sl and sr:
        top = min(sl[1], sr[1]) - int(height * 0.05)
    elif sl or sr:
        top = (sl or sr)[1] - int(height * 0.05)
    else:
        top = y1 + int(height * 0.20)

    if hl and hr:
        bottom = max(hl[1], hr[1]) + int(height * 0.05)
    elif hl or hr:
        bottom = (hl or hr)[1] + int(height * 0.05)
    else:
        bottom = y1 + int(height * 0.62)

    xs = [p[0] for p in (sl, sr, hl, hr) if p]
    if len(xs) >= 2:
        pad = int(height * 0.06)
        left, right = min(xs) - pad, max(xs) + pad
    else:
        left, right = x1 + 2, x2 - 2

    return (max(0, left), max(0, top),
            min(frame_w - 1, right), min(frame_h - 1, bottom))


def head_geometry(box, kps):
    """Devolve (centro_x, meia_largura, topo, queixo) da cabeca.

    Ancora nos ombros porque eles chegam com confianca alta (0.9+). De
    perfil ou de costas o YOLO estima nariz e olhos em posicao errada com
    confianca marginal; se eles ancorarem o recorte, ele sai da cabeca.
    Por isso os keypoints faciais so entram como refinamento, e apenas
    quando sao coerentes com a cabeca derivada dos ombros.
    """
    x1, y1, x2, y2 = box
    nose = keypoint(kps, NOSE)
    eye_l, eye_r = keypoint(kps, EYE_L), keypoint(kps, EYE_R)
    ear_l, ear_r = keypoint(kps, EAR_L), keypoint(kps, EAR_R)
    sl, sr = keypoint(kps, SHOULDER_L), keypoint(kps, SHOULDER_R)

    top = float(y1)  # o YOLO fecha a caixa no topo do cranio

    if sl and sr:
        shoulder_w = abs(sr[0] - sl[0])
        cx = (sl[0] + sr[0]) / 2.0
        # escala vertical medida direta: cranio -> ombro
        span = max(8.0, min(sl[1], sr[1]) - top)
        half_w = float(np.clip(max(shoulder_w * 0.46, span * 0.60),
                               9.0, (x2 - x1) * 0.80))
        chin = top + span * 0.80
    else:
        half_w = float(np.clip((x2 - x1) * 0.34, 9.0, (x2 - x1) * 0.80))
        cx = (x1 + x2) / 2.0
        chin = top + (y2 - y1) * 0.16

    face_x = [p[0] for p in (nose, eye_l, eye_r, ear_l, ear_r) if p]
    if face_x:
        candidate = sum(face_x) / len(face_x)
        if abs(candidate - cx) < half_w * 0.90:
            cx = candidate

    if nose and top + (chin - top) * 0.25 < nose[1] < chin + (chin - top) * 0.35:
        chin = nose[1] + (chin - top) * 0.30  # o nariz fica a ~70% do queixo

    return float(cx), float(half_w), float(top), float(chin)


def helmet_roi(box, kps, frame_w: int, frame_h: int):
    """Calota da cabeca onde o capacete deve aparecer."""
    cx, half_w, top, chin = head_geometry(box, kps)
    bottom = top + (chin - top) * 0.55  # meio da cabeca, acima das orelhas
    if bottom - top < 4:
        bottom = top + 4
    left, right = cx - half_w * 0.62, cx + half_w * 0.62
    return (max(0, int(left)), max(0, int(top)),
            min(frame_w - 1, int(right)), min(frame_h - 1, int(bottom)))


def _skin_mask(hsv):
    """Tom de pele: matiz alaranjado com saturacao media.

    O teto de saturacao importa. Pele raramente passa de ~175, enquanto
    capacete laranja pintado fica bem acima. Sem esse limite a mascara
    engolia o capacete e o classificava como cabeca descoberta.
    """
    low = cv2.inRange(hsv, np.array([0, 35, 70]), np.array([22, 175, 255]))
    high = cv2.inRange(hsv, np.array([168, 35, 70]), np.array([180, 175, 255]))
    return low | high


def vest_coverage(frame, roi) -> float:
    """Fracao do tronco coberta por cor de colete refletivo."""
    x1, y1, x2, y2 = roi
    if x2 - x1 < 4 or y2 - y1 < 4:
        return 0.0
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return 0.0

    hsv = cv2.cvtColor(cv2.GaussianBlur(patch, (3, 3), 0), cv2.COLOR_BGR2HSV)
    mask = np.zeros(patch.shape[:2], np.uint8)
    for low, high in VEST_HSV:
        mask |= cv2.inRange(hsv, np.array(low), np.array(high))

    # o refletivo cria buracos na mascara; fechar evita subestimar
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    total = patch.shape[0] * patch.shape[1]
    return np.count_nonzero(mask) / total if total else 0.0


def helmet_coverage(frame, roi) -> float:
    """Fracao da calota coberta por algo com aparencia de capacete.

    Mede dentro de uma meia-elipse, nao do retangulo, para o fundo atras
    da cabeca nao entrar na conta. Uma cabeca distante ocupa ~20 px, o
    que nao da estatistica suficiente, entao o recorte e ampliado antes
    da analise.
    """
    x1, y1, x2, y2 = roi
    if x2 - x1 < 5 or y2 - y1 < 3:
        return 0.0
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return 0.0

    h, w = patch.shape[:2]
    if w < 64 or h < 40:
        scale = max(64 / max(w, 1), 40 / max(h, 1))
        patch = cv2.resize(patch,
                           (max(64, int(w * scale)), max(40, int(h * scale))),
                           interpolation=cv2.INTER_CUBIC)
        h, w = patch.shape[:2]

    dome = np.zeros((h, w), np.uint8)
    cv2.ellipse(dome, (w // 2, h), (int(w * 0.50), int(h * 0.98)),
                0, 180, 360, 255, -1)
    area = np.count_nonzero(dome)
    if area < 40:
        return 0.0

    hsv = cv2.cvtColor(cv2.GaussianBlur(patch, (3, 3), 0), cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

    skin = _skin_mask(hsv)
    hair_dark = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 72]))
    hair_dull = cv2.inRange(hsv, np.array([0, 0, 72]), np.array([180, 42, 150]))
    rejected = skin | hair_dark | hair_dull

    best = 0.0

    # capacete colorido: matiz industrial, saturado e de superficie lisa
    for low, high in HELMET_HUES:
        mask = cv2.inRange(hsv, np.array([low, 75, 70]),
                           np.array([min(179, high), 255, 255]))
        mask = cv2.bitwise_and(mask, dome)
        mask = cv2.bitwise_and(mask, cv2.bitwise_not(rejected))
        coverage = np.count_nonzero(mask) / area
        if coverage < 0.22:
            continue
        pixels = gray[mask > 0]
        if len(pixels) == 0 or np.std(pixels) > 62:
            continue  # textura alta = cabelo, nao plastico
        best = max(best, coverage)

    # capacete branco: quase sem saturacao, mas muito claro e uniforme
    white = cv2.inRange(hsv, np.array([0, 0, 190]), np.array([180, 48, 255]))
    white = cv2.bitwise_and(white, dome)
    white = cv2.bitwise_and(white, cv2.bitwise_not(skin))
    coverage = np.count_nonzero(white) / area
    if coverage >= 0.28:
        pixels = gray[white > 0]
        if len(pixels) > 0 and np.std(pixels) <= 46:
            best = max(best, coverage)

    return best


class EPIDetector:
    """Envolve o YOLO e a analise de EPI numa chamada por frame."""

    def __init__(self, model_path: str | None = None, imgsz: int | None = None):
        self.model = YOLO(model_path or config.MODEL_PATH)
        self.imgsz = imgsz or config.INPUT_SIZE

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        result = self.model(frame, conf=config.CONF_THRESH,
                            imgsz=self.imgsz, verbose=False)[0]

        if result.boxes is None or not len(result.boxes):
            return []

        classes = result.boxes.cls.cpu().numpy()
        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        kp_xy = (result.keypoints.xy.cpu().numpy()
                 if result.keypoints is not None else None)
        kp_cf = (result.keypoints.conf.cpu().numpy()
                 if result.keypoints is not None
                 and result.keypoints.conf is not None else None)

        found: list[Detection] = []
        for i in range(len(boxes)):
            if int(classes[i]) != 0:  # classe 0 = pessoa
                continue

            x1, y1, x2, y2 = (int(v) for v in boxes[i])
            box_w, box_h = x2 - x1, y2 - y1
            if box_w < 12 or box_h < 24:
                continue
            # reflexo no piso chega como caixa achatada; pessoa e mais alta
            if box_w / max(box_h, 1) > config.MAX_ASPECT:
                continue

            kps = None
            if kp_xy is not None and i < len(kp_xy):
                kps = []
                for j in range(kp_xy.shape[1]):
                    x, y = float(kp_xy[i, j, 0]), float(kp_xy[i, j, 1])
                    conf = float(kp_cf[i, j]) if kp_cf is not None else 1.0
                    if x <= 0 and y <= 0:
                        conf = 0.0
                    kps.append((x, y, conf))
                # pessoa real gera pose coerente; fantasma da 1-2 pontos
                usable = sum(1 for p in kps
                             if p[2] >= config.KEYPOINT_MIN_CONF)
                if usable < config.MIN_KEYPOINTS:
                    continue

            box = (x1, y1, x2, y2)
            v_roi = vest_roi(box, kps, w, h)
            h_roi = helmet_roi(box, kps, w, h)
            v_score = vest_coverage(frame, v_roi)
            h_score = helmet_coverage(frame, h_roi)

            found.append(Detection(
                box=box, keypoints=kps, confidence=float(confs[i]),
                has_vest=v_score >= config.VEST_THRESH,
                has_helmet=h_score >= config.HELMET_THRESH,
                vest_score=v_score, helmet_score=h_score,
                vest_roi=v_roi, helmet_roi=h_roi,
            ))

        return _drop_duplicates(found)


def _drop_duplicates(dets: list[Detection]) -> list[Detection]:
    """Descarta caixas repetidas sobre a mesma pessoa.

    IoU nao resolve em plano fechado: duas caixas grandes e deslocadas
    sobre o mesmo operador ficam em IoU proximo de 0.44, abaixo de
    qualquer corte razoavel. O rosto e o sinal confiavel: se dois rostos
    coincidem, e a mesma pessoa.
    """
    keep: list[Detection] = []
    for det in sorted(dets, key=lambda d: -d.confidence):
        if not any(_same_person(det, other) for other in keep):
            keep.append(det)
    return keep


def _same_person(a: Detection, b: Detection) -> bool:
    ax1, ay1, ax2, ay2 = a.box
    bx1, by1, bx2, by2 = b.box
    inter = (max(0, min(ax2, bx2) - max(ax1, bx1)) *
             max(0, min(ay2, by2) - max(ay1, by1)))
    smaller = min((ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1))
    if smaller > 0 and inter / smaller > 0.65:
        return True

    fa, fb = face_center(a.keypoints), face_center(b.keypoints)
    if fa and fb:
        scale = max(ax2 - ax1, bx2 - bx1, 1)
        dist = ((fa[0] - fb[0]) ** 2 + (fa[1] - fb[1]) ** 2) ** 0.5
        if dist < scale * 0.20:
            return True
    return False


def pick_input_size(model, cap, total_frames: int,
                    frame_h: int) -> tuple[int, float]:
    """Escolhe imgsz medindo quanto do quadro as pessoas ocupam.

    Nao existe um valor bom para todos os casos. Medido em material real:
    pessoas a cerca de 150 px exigem 1280, e em 896 duas desaparecem. Ja
    em plano fechado 768 acerta mais que 1280 e roda cerca de tres vezes
    mais rapido, porque o YOLO responde por quase todo o custo por frame.
    """
    heights = []
    for fraction in (0.2, 0.5, 0.8):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * fraction))
        ok, frame = cap.read()
        if not ok:
            continue
        result = model(frame, conf=config.CONF_THRESH,
                       imgsz=config.INPUT_SIZE, verbose=False)[0]
        if result.boxes is None:
            continue
        classes = result.boxes.cls.cpu().numpy()
        boxes = result.boxes.xyxy.cpu().numpy()
        for i in range(len(boxes)):
            if int(classes[i]) != 0:
                continue
            box_h = boxes[i][3] - boxes[i][1]
            if box_h > 24:
                heights.append(box_h / frame_h)

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    if not heights:
        return config.INPUT_SIZE, 0.0

    median = float(np.median(heights))
    size = config.INPUT_SIZE_NEAR if median >= 0.30 else config.INPUT_SIZE
    return size, median

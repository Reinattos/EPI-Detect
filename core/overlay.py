"""
Camada visual: esqueleto, rotulos e painel de status sobre o frame.

Duas decisoes de desenho valem registro, porque as duas vieram de
tentativa e erro:

1. O esqueleto e colorido por zona de EPI, nao por pessoa. Tronco e
   bracos seguem o colete, cabeca e face seguem o capacete, pernas ficam
   num tom neutro por nao serem monitoradas. Isso deixa a violacao
   parcial legivel sem ler texto: tronco verde e cabeca vermelha diz
   "tem colete, falta capacete" numa olhada.

2. Nada e desenhado sobre o rosto. Uma versao anterior marcava a cabeca
   descoberta com uma reticula centrada nela, o que cobria exatamente o
   que o operador de camera precisa ver. A marca de capacete ausente
   ficou como um arco acima da cabeca.

A espessura acompanha o tamanho da pessoa no quadro: em plano fechado
uma linha fixa vira borrao, em plano aberto desaparece.
"""

from __future__ import annotations

import cv2
import numpy as np

import config

# BGR
GREEN = (34, 197, 94)
RED = (54, 54, 220)
YELLOW = (21, 204, 250)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
NEUTRAL = (150, 140, 120)
ACCENT = (205, 180, 70)
PANEL = (12, 16, 24)
LINE = (42, 54, 70)

# Esqueleto COCO-17 agrupado por zona de EPI.
BONES_HEAD = ((0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6))
BONES_TORSO = ((5, 6), (5, 11), (6, 12), (11, 12),
               (5, 7), (7, 9), (6, 8), (8, 10))
BONES_LEGS = ((11, 13), (13, 15), (12, 14), (14, 16))

KP_HEAD = (0, 1, 2, 3, 4)
KP_TORSO = (5, 6, 7, 8, 9, 10, 11, 12)
KP_LEGS = (13, 14, 15, 16)

FONT = cv2.FONT_HERSHEY_DUPLEX


def _point(kps, index):
    if kps is None or index >= len(kps):
        return None
    x, y, conf = kps[index]
    if conf < config.KEYPOINT_MIN_CONF or (x <= 0 and y <= 0):
        return None
    return int(x), int(y)


def draw_skeleton(img, kps, head_color, torso_color, scale: float = 1.0):
    """Esqueleto com cor por zona de EPI."""
    if kps is None:
        return
    thickness = int(np.clip(round(2 * scale), 2, 4))
    radius = int(np.clip(round(3 * scale), 2, 5))

    for bones, color in ((BONES_LEGS, NEUTRAL),
                         (BONES_TORSO, torso_color),
                         (BONES_HEAD, head_color)):
        for a, b in bones:
            pa, pb = _point(kps, a), _point(kps, b)
            if pa and pb:
                # contorno escuro mantem contraste sobre fundo claro
                cv2.line(img, pa, pb, BLACK, thickness + 2, cv2.LINE_AA)
                cv2.line(img, pa, pb, color, thickness, cv2.LINE_AA)

    for indices, color in ((KP_LEGS, NEUTRAL),
                           (KP_TORSO, torso_color),
                           (KP_HEAD, head_color)):
        for i in indices:
            p = _point(kps, i)
            if p:
                cv2.circle(img, p, radius + 1, BLACK, -1, cv2.LINE_AA)
                cv2.circle(img, p, radius, color, -1, cv2.LINE_AA)


def draw_box(img, box, color, thickness: int = 2):
    """Cantos em L. Caixa fechada polui e nao acrescenta informacao."""
    x1, y1, x2, y2 = box
    length = int(np.clip(min(x2 - x1, y2 - y1) * 0.16, 10, 28))
    for cx, cy, dx, dy in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                           (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(img, (cx, cy), (cx + dx * length, cy), BLACK, thickness + 2, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + dy * length), BLACK, thickness + 2, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx + dx * length, cy), color, thickness, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + dy * length), color, thickness, cv2.LINE_AA)


def draw_dashed_box(img, box, color, dash: int = 6, thickness: int = 1):
    """Contorno tracejado, usado para as zonas de analise."""
    x1, y1, x2, y2 = box
    for x in range(x1, x2, dash * 2):
        cv2.line(img, (x, y1), (min(x + dash, x2), y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x, y2), (min(x + dash, x2), y2), color, thickness, cv2.LINE_AA)
    for y in range(y1, y2, dash * 2):
        cv2.line(img, (x1, y), (x1, min(y + dash, y2)), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y), (x2, min(y + dash, y2)), color, thickness, cv2.LINE_AA)


def draw_missing_helmet(img, helmet_roi, scale: float):
    """Arco tracejado ACIMA da cabeca: o capacete que deveria estar ali.

    Fica fora da face de proposito, para nao esconder a pessoa.
    """
    x1, y1, x2, y2 = helmet_roi
    if x2 - x1 < 8:
        return
    cx = (x1 + x2) // 2
    rx = int((x2 - x1) * 0.60)
    ry = max(5, int((y2 - y1) * 0.85))
    top = y1 - max(4, int(6 * scale))
    for angle in range(186, 355, 22):
        cv2.ellipse(img, (cx, top), (rx, ry), 0, angle, angle + 13, BLACK, 4, cv2.LINE_AA)
        cv2.ellipse(img, (cx, top), (rx, ry), 0, angle, angle + 13, RED, 2, cv2.LINE_AA)


def draw_label(img, text, x, y, background, text_color=BLACK, size: float = 0.40):
    (tw, th), baseline = cv2.getTextSize(text, FONT, size, 1)
    pad = 6
    cv2.rectangle(img, (x - 1, y - th - pad - 1),
                  (x + tw + pad * 2 + 1, y + baseline + 1), BLACK, -1)
    cv2.rectangle(img, (x, y - th - pad), (x + tw + pad * 2, y + baseline),
                  background, -1)
    cv2.putText(img, text, (x + pad, y), FONT, size, text_color, 1, cv2.LINE_AA)


def draw_detections(img, detections, fps: float, video_width: int):
    """Desenha zonas de analise, esqueleto, caixa e rotulos de cada pessoa."""
    for det in detections:
        x1, y1, x2, y2 = det.box
        if x1 >= video_width - 8:  # coberta pelo painel lateral
            continue

        head_color = YELLOW if det.has_helmet else RED
        torso_color = GREEN if det.has_vest else RED
        box_color = GREEN if det.compliant else RED
        scale = float(np.clip((y2 - y1) / 220.0, 0.7, 2.2))

        if config.SHOW_ANALYSIS_ZONES:
            if det.vest_roi:
                draw_dashed_box(img, det.vest_roi, torso_color)
            if det.helmet_roi:
                draw_dashed_box(img, det.helmet_roi, head_color)

        if not det.has_helmet and det.helmet_roi:
            draw_missing_helmet(img, det.helmet_roi, scale)

        draw_skeleton(img, det.keypoints, head_color, torso_color, scale)
        draw_box(img, (x1, y1, min(x2, video_width - 2), y2), box_color)

        # rotulos acima da cabeca; a marca de capacete ausente ocupa a
        # faixa logo acima do recorte, entao o texto sobe um pouco mais
        roi = det.helmet_roi or (x1, y1, x2, y2)
        gap = int((roi[3] - roi[1]) * 0.9) + 14 if not det.has_helmet else 8
        lx = int(np.clip(roi[0] - 4, 4, video_width - 136))
        ly = max(62, roi[1] - gap)

        seconds = det.violation_frames / max(fps, 1.0)
        suffix = f"  {seconds:.0f}s" if seconds >= 1.0 else ""

        draw_label(img, "CAPACETE OK" if det.has_helmet else "SEM CAPACETE" + suffix,
                   lx, ly - 21, YELLOW if det.has_helmet else RED,
                   BLACK if det.has_helmet else WHITE)
        draw_label(img, "COLETE OK" if det.has_vest else "SEM COLETE" + suffix,
                   lx, ly, GREEN if det.has_vest else RED,
                   BLACK if det.has_vest else WHITE)


def draw_header(img, camera_name: str, clock: str, progress: float = 0.0):
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, 0), (w, 40), PANEL, -1)
    cv2.line(img, (0, 40), (w, 40), LINE, 1)

    cv2.putText(img, camera_name, (14, 26), FONT, 0.38, ACCENT, 1, cv2.LINE_AA)
    cv2.putText(img, clock, (86, 26), FONT, 0.50, (175, 205, 175), 1, cv2.LINE_AA)

    title = config.SYSTEM_TITLE
    (tw, _), _ = cv2.getTextSize(title, FONT, 0.44, 1)
    cv2.putText(img, title, ((w - tw) // 2, 26), FONT, 0.44, WHITE, 1, cv2.LINE_AA)

    if progress > 0:
        cv2.rectangle(img, (0, 38), (int(w * progress), 40), ACCENT, -1)


def draw_live_badge(img, blink: bool = True):
    h, w = img.shape[:2]
    if blink:
        cv2.circle(img, (w - 214, 20), 5, RED, -1, cv2.LINE_AA)
    cv2.putText(img, "AO VIVO", (w - 202, 25), FONT, 0.36, (80, 80, 220), 1, cv2.LINE_AA)


def draw_sidebar(img, counts, fps: float, pulse: float = 0.0):
    """Painel lateral com contadores, conformidade e legenda."""
    h, w = img.shape[:2]
    width = config.SIDEBAR_WIDTH
    px = w - width
    cv2.rectangle(img, (px, 0), (w, h), PANEL, -1)
    cv2.line(img, (px, 0), (px, h), LINE, 1)
    x = px + 16

    def text(value, y, color=WHITE, size=0.38, bold=False):
        cv2.putText(img, value, (x, y), FONT, size, color, 2 if bold else 1, cv2.LINE_AA)

    text("EPI DETECT", 32, ACCENT, 0.58, True)
    text("MONITORAMENTO DE SEGURANCA", 50, (95, 115, 135), 0.30)
    cv2.line(img, (x, 62), (w - 16, 62), LINE, 1)

    # numero grande a esquerda, rotulo a direita: le mais rapido que
    # rotulo em cima e numero embaixo
    y = 96
    for label, value, color in (("CONFORMES", counts["ok"], GREEN),
                                ("SEM COLETE", counts["no_vest"], RED),
                                ("SEM CAPACETE", counts["no_helmet"], RED),
                                ("TOTAL", counts["total"], WHITE)):
        cv2.putText(img, str(value), (x, y), FONT, 1.05,
                    color if value else (58, 68, 80), 2, cv2.LINE_AA)
        cv2.putText(img, label, (x + 46, y - 6), FONT, 0.34,
                    (140, 158, 175), 1, cv2.LINE_AA)
        y += 48

    cv2.line(img, (x, y - 14), (w - 16, y - 14), LINE, 1)

    total = counts["total"]
    percent = int(counts["ok"] / total * 100) if total else 0
    bar_color = GREEN if percent >= 80 else YELLOW if percent >= 50 else RED
    text("CONFORMIDADE", y + 8, (140, 158, 175), 0.34)
    cv2.putText(img, f"{percent}%", (w - 70, y + 9), FONT, 0.50,
                bar_color, 1, cv2.LINE_AA)
    y += 20
    bar_w = width - 32
    cv2.rectangle(img, (x, y), (x + bar_w, y + 9), (30, 38, 50), -1)
    cv2.rectangle(img, (x, y), (x + int(bar_w * percent / 100), y + 9), bar_color, -1)
    y += 34

    cv2.line(img, (x, y - 14), (w - 16, y - 14), LINE, 1)
    text("LEGENDA", y + 4, (110, 130, 150), 0.32)
    y += 24
    for color, label in ((YELLOW, "capacete detectado"),
                         (GREEN, "colete detectado"),
                         (RED, "EPI ausente"),
                         (NEUTRAL, "nao monitorado")):
        cv2.line(img, (x, y - 4), (x + 20, y - 4), color, 4, cv2.LINE_AA)
        cv2.putText(img, label, (x + 28, y), FONT, 0.33,
                    (150, 168, 185), 1, cv2.LINE_AA)
        y += 23

    alert = counts["no_vest"] > 0 or counts["no_helmet"] > 0
    footer_y = h - 74 if alert else h - 16
    cv2.line(img, (x, footer_y - 24), (w - 16, footer_y - 24), LINE, 1)
    cv2.circle(img, (x + 4, footer_y - 8), 3, GREEN, -1, cv2.LINE_AA)
    cv2.putText(img, f"YOLOv8n-pose  {fps:.0f} fps", (x + 14, footer_y - 4),
                FONT, 0.31, (105, 125, 150), 1, cv2.LINE_AA)

    if alert:
        ay = h - 62
        cv2.rectangle(img, (px + 1, ay), (w - 1, h), (28, 28, 120), -1)
        cv2.rectangle(img, (px + 1, ay), (w - 1, h),
                      (60, 60, int(190 + 60 * pulse)), 1)
        missing = []
        if counts["no_vest"]:
            missing.append(f"{counts['no_vest']} sem colete")
        if counts["no_helmet"]:
            missing.append(f"{counts['no_helmet']} sem capacete")
        cv2.putText(img, "ALERTA", (x, ay + 24), FONT, 0.44,
                    (120, 120, 255), 1, cv2.LINE_AA)
        cv2.putText(img, "  ".join(missing) or "violacao", (x, ay + 46),
                    FONT, 0.33, (165, 165, 255), 1, cv2.LINE_AA)


def make_canvas(frame):
    """Cria uma tela mais larga: video intacto a esquerda, painel a direita.

    Sobrepor o painel ao video custava os 235 px da direita da imagem, e
    naquela faixa costuma cair marca de agua ou relogio da camera. Somando
    a largura em vez de sobrepor, nada do quadro original e perdido.
    """
    h, w = frame.shape[:2]
    canvas = np.zeros((h, w + config.SIDEBAR_WIDTH, 3), np.uint8)
    canvas[:, :w] = frame
    return canvas


def blur_region(img, box, sigma: int = 18, darken: float = 0.55):
    """Desfoca e escurece um retangulo, com borda suave.

    Serve para neutralizar marca de agua ou relogio gravado no video de
    origem. Retangulo solido lia como defeito de encoding; o desfoque com
    borda difusa lê como tarja intencional.
    """
    x1, y1, x2, y2 = box
    region = img[y1:y2, x1:x2]
    if region.size == 0:
        return
    soft = (cv2.GaussianBlur(region, (0, 0), sigma) * darken).astype(np.uint8)
    mask = np.zeros(region.shape[:2], np.float32)
    cv2.rectangle(mask, (10, 10), (region.shape[1] - 10, region.shape[0] - 10), 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), 9)[..., None]
    img[y1:y2, x1:x2] = (soft * mask + region * (1 - mask)).astype(np.uint8)

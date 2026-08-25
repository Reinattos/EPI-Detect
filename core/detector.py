from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

import config as cfg

_PROJECT_ROOT = Path(__file__).parent.parent

# Pares de keypoints COCO para desenhar o esqueleto
SKELETON_PAIRS = [
    (5, 6),  # ombros
    (5, 7),
    (7, 9),  # braço esquerdo
    (6, 8),
    (8, 10),  # braço direito
    (5, 11),
    (6, 12),  # lados do torso
    (11, 12),  # quadril
    (11, 13),
    (13, 15),  # perna esquerda
    (12, 14),
    (14, 16),  # perna direita
    (0, 5),
    (0, 6),  # nariz → ombros
]


def is_vest_evidence(coverage: float, left_cov: float, right_cov: float) -> bool:
    """Aplica a regra HSV sem depender do carregamento do modelo YOLO."""
    return (
        coverage >= cfg.VEST_THRESH
        and left_cov >= cfg.VEST_SIDE_THRESH
        and right_cov >= cfg.VEST_SIDE_THRESH
    )


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    has_vest: bool
    vest_coverage: float
    person_conf: float
    keypoints: np.ndarray | None = field(default=None, repr=False)  # (17, 3) x,y,conf


class EPIDetector:
    def __init__(self):
        import torch

        torch.set_num_threads(cfg.TORCH_THREADS)
        torch.set_num_interop_threads(1)
        from ultralytics import YOLO

        model_path = _PROJECT_ROOT / cfg.MODEL_NAME
        # Usa o peso local quando existe; caso contrario, a Ultralytics baixa
        # o modelo oficial pelo nome na primeira execucao.
        model_source = str(model_path) if model_path.exists() else cfg.MODEL_NAME
        self._model = YOLO(model_source)
        dummy = np.zeros((cfg.INPUT_SIZE, cfg.INPUT_SIZE, 3), dtype=np.uint8)
        self._model(dummy, verbose=False, device="cpu")

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self._model(
            frame,
            imgsz=cfg.INPUT_SIZE,
            conf=cfg.CONF_THRESH,
            verbose=False,
            device="cpu",
        )

        detections = []
        boxes = results[0].boxes
        if boxes is None:
            return detections

        kps_data = results[0].keypoints
        h_frame, w_frame = frame.shape[:2]

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_frame, x2), min(h_frame, y2)

            bw, bh = x2 - x1, y2 - y1

            # Filtro anti-falso-positivo: cones, paletes e objetos têm ratio baixo
            if bh < cfg.MIN_PERSON_HEIGHT:
                continue
            if bw > 0 and bh / bw < cfg.MIN_PERSON_RATIO:
                continue

            # Keypoints desta pessoa
            kps = None
            if kps_data is not None and i < len(kps_data.data):
                kps = kps_data.data[i].cpu().numpy()  # (17, 3)

            coverage, left_cov, right_cov = self._vest_coverage(frame, x1, y1, x2, y2, kps)
            has_vest = is_vest_evidence(coverage, left_cov, right_cov)

            detections.append(
                Detection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    has_vest=has_vest,
                    vest_coverage=coverage,
                    person_conf=float(box.conf[0]),
                    keypoints=kps,
                )
            )

        return detections

    def _vest_coverage(self, frame, x1, y1, x2, y2, keypoints=None):
        h_frame, w_frame = frame.shape[:2]

        # Tenta usar ombro/quadril dos keypoints para torso preciso
        if keypoints is not None:
            ls, rs = keypoints[5], keypoints[6]  # ombro esquerdo/direito
            lh, rh = keypoints[11], keypoints[12]  # quadril esquerdo/direito
            sh_conf = min(float(ls[2]), float(rs[2]))
            hip_conf = min(float(lh[2]), float(rh[2]))

            if sh_conf > cfg.KP_CONF_THRESH and hip_conf > cfg.KP_CONF_THRESH:
                top_y = max(0, int(min(ls[1], rs[1])))
                bot_y = min(h_frame, int(max(lh[1], rh[1])))
                left_x = max(0, int(min(ls[0], lh[0])) - 8)
                right_x = min(w_frame, int(max(rs[0], rh[0])) + 8)

                if bot_y > top_y and right_x > left_x:
                    torso = frame[top_y:bot_y, left_x:right_x]
                    if torso.size > 0:
                        return self._hsv_coverage(torso)

        # Fallback: percentual da bounding box (pescoço→quadril)
        box_h = y2 - y1
        crop_y1 = y1 + int(box_h * cfg.TORSO_TOP)
        crop_y2 = y1 + int(box_h * cfg.TORSO_BOTTOM)
        torso = frame[crop_y1:crop_y2, x1:x2]
        if torso.size == 0:
            return 0.0, 0.0, 0.0
        return self._hsv_coverage(torso)

    def _hsv_coverage(self, torso):
        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, cfg.ORANGE_LOW, cfg.ORANGE_HIGH) | cv2.inRange(
            hsv, cfg.YELLOW_LOW, cfg.YELLOW_HIGH
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        height, width = torso.shape[:2]
        total = height * width
        if total <= 0 or width < 2:
            return 0.0, 0.0, 0.0

        mid = width // 2
        left_total = height * mid
        right_total = height * (width - mid)
        coverage = float(np.count_nonzero(mask)) / total
        left_cov = float(np.count_nonzero(mask[:, :mid])) / left_total
        right_cov = float(np.count_nonzero(mask[:, mid:])) / right_total
        return coverage, left_cov, right_cov

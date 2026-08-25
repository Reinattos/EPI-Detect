import time

import cv2
import numpy as np

import config as cfg
from core.detector import SKELETON_PAIRS, Detection

_GREEN = cfg.COLOR_OK
_RED = cfg.COLOR_WARN
_YELLOW = cfg.COLOR_INFO
_DARK = (20, 20, 20)
_GRAY = (130, 130, 130)
_WHITE = (240, 240, 240)


def _blend(img, x1, y1, x2, y2, color, alpha=0.55):
    sub = img[y1:y2, x1:x2]
    if sub.size == 0:
        return
    rect = np.full(sub.shape, color, dtype=np.uint8)
    cv2.addWeighted(rect, alpha, sub, 1 - alpha, 0, sub)
    img[y1:y2, x1:x2] = sub


def _label(img, x, y, text, color, scale=0.52, thick=1, pad=5):
    font = cv2.FONT_HERSHEY_DUPLEX
    (tw, th), base = cv2.getTextSize(text, font, scale, thick)
    th += base
    bx1, by1 = max(0, x), max(0, y - th - pad * 2)
    bx2, by2 = bx1 + tw + pad * 2, by1 + th + pad * 2
    _blend(img, bx1, by1, bx2, by2, color, alpha=0.85)
    cv2.putText(img, text, (bx1 + pad, by2 - pad), font, scale, _WHITE, thick, cv2.LINE_AA)


def _torso_box(kps, frame_h: int, frame_w: int) -> tuple[int, int, int, int] | None:
    """Retorna (x1,y1,x2,y2) do torso via keypoints de ombro/quadril, ou None."""
    if kps is None:
        return None
    ls, rs = kps[5], kps[6]  # ombros
    lh, rh = kps[11], kps[12]  # quadril
    if min(float(ls[2]), float(rs[2])) < cfg.KP_CONF_THRESH:
        return None
    if min(float(lh[2]), float(rh[2])) < cfg.KP_CONF_THRESH:
        return None
    ty1 = max(0, int(min(ls[1], rs[1])) - 6)
    ty2 = min(frame_h, int(max(lh[1], rh[1])) + 6)
    tx1 = max(0, int(min(ls[0], lh[0])) - 12)
    tx2 = min(frame_w, int(max(rs[0], rh[0])) + 12)
    if ty2 > ty1 + 10 and tx2 > tx1 + 10:
        return tx1, ty1, tx2, ty2
    return None


def _draw_skeleton(img, kps, color):
    if kps is None:
        return
    dim = tuple(max(0, int(c * 0.6)) for c in color)
    for a, b in SKELETON_PAIRS:
        xa, ya, ca = kps[a]
        xb, yb, cb = kps[b]
        if ca > cfg.KP_CONF_THRESH and cb > cfg.KP_CONF_THRESH:
            cv2.line(img, (int(xa), int(ya)), (int(xb), int(yb)), dim, 2, cv2.LINE_AA)
    for kp in kps:
        x, y, c = kp
        if c > cfg.KP_CONF_THRESH:
            cv2.circle(img, (int(x), int(y)), 3, color, -1, cv2.LINE_AA)


class Renderer:
    def __init__(self, mode: str = "LIVE"):
        self.mode = mode
        self._fps_times: list = []
        self._font = cv2.FONT_HERSHEY_DUPLEX

    def render(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        self._update_fps()
        out = frame.copy()
        self._draw_detections(out, detections)
        self._draw_header(out)
        self._draw_status_bar(out, detections)
        return out

    def _draw_detections(self, img, detections):
        h, w = img.shape[:2]
        for d in detections:
            color = _GREEN if d.has_vest else _RED

            # ── Esqueleto (completo, tons escuros) ───────────────────────
            _draw_skeleton(img, d.keypoints, color)

            # ── Outline corpo inteiro (sutil) ─────────────────────────────
            cv2.rectangle(
                img, (d.x1, d.y1), (d.x2, d.y2), tuple(max(0, int(c * 0.4)) for c in color), 1
            )

            # ── Box torso (destaque principal) ────────────────────────────
            tb = _torso_box(d.keypoints, h, w)
            if tb:
                tx1, ty1, tx2, ty2 = tb
                # sombra externa
                cv2.rectangle(img, (tx1 - 1, ty1 - 1), (tx2 + 1, ty2 + 1), (0, 0, 0), 2)
                # retângulo principal colorido
                cv2.rectangle(img, (tx1, ty1), (tx2, ty2), color, 2)
                # cantos táticos
                cs = 12
                for cx, cy, dx, dy in [
                    (tx1, ty1, 1, 1),
                    (tx2, ty1, -1, 1),
                    (tx1, ty2, 1, -1),
                    (tx2, ty2, -1, -1),
                ]:
                    cv2.line(img, (cx, cy), (cx + dx * cs, cy), color, 3)
                    cv2.line(img, (cx, cy), (cx, cy + dy * cs), color, 3)
                # label acima do torso box
                # vest_coverage e a fracao de pixels fluorescentes, nao uma
                # confianca nem a porcentagem fisica do colete. Nao exibir o
                # valor evita uma leitura enganosa para o operador.
                label = "EPI DETECTADO" if d.has_vest else "SEM EPI"
                _label(img, tx1, ty1, label, color)
            else:
                # Fallback: box completo quando não há keypoints de torso
                cv2.rectangle(img, (d.x1 - 1, d.y1 - 1), (d.x2 + 1, d.y2 + 1), (0, 0, 0), 2)
                cv2.rectangle(img, (d.x1, d.y1), (d.x2, d.y2), color, 2)
                cs = 14
                for cx, cy, dx, dy in [
                    (d.x1, d.y1, 1, 1),
                    (d.x2, d.y1, -1, 1),
                    (d.x1, d.y2, 1, -1),
                    (d.x2, d.y2, -1, -1),
                ]:
                    cv2.line(img, (cx, cy), (cx + dx * cs, cy), color, 3)
                    cv2.line(img, (cx, cy), (cx, cy + dy * cs), color, 3)
                label = "EPI DETECTADO" if d.has_vest else "SEM EPI"
                _label(img, d.x1, d.y1, label, color)

    def _draw_header(self, img):
        h, w = img.shape[:2]
        bar_h = 44
        _blend(img, 0, 0, w, bar_h, _DARK, alpha=0.72)
        cv2.line(img, (0, bar_h), (w, bar_h), (50, 50, 50), 1)
        cv2.putText(img, "EPI DETECT", (14, 30), self._font, 0.75, _WHITE, 1, cv2.LINE_AA)
        badge = self.mode
        badge_color = (180, 100, 30) if self.mode == "LIVE" else (160, 60, 160)
        bw, bx = 58, 180
        _blend(img, bx, 10, bx + bw, 35, badge_color, alpha=0.9)
        cv2.putText(img, badge, (bx + 8, 29), self._font, 0.45, _WHITE, 1, cv2.LINE_AA)
        ts = time.strftime("%H:%M:%S")
        tw, _ = cv2.getTextSize(ts, self._font, 0.45, 1)[0]
        cv2.putText(img, ts, (w - tw - 14, 29), self._font, 0.45, _GRAY, 1, cv2.LINE_AA)

    def _draw_status_bar(self, img, detections):
        h, w = img.shape[:2]
        bar_h = 50
        _blend(img, 0, h - bar_h, w, h, _DARK, alpha=0.72)
        cv2.line(img, (0, h - bar_h), (w, h - bar_h), (50, 50, 50), 1)
        with_vest = sum(1 for d in detections if d.has_vest)
        without_vest = sum(1 for d in detections if not d.has_vest)
        fps = self._current_fps()
        col_w = w // 3
        items = [
            (f"COM EPI:  {with_vest}", _GREEN, 20),
            (f"SEM EPI:  {without_vest}", _RED, col_w + 20),
            (f"PESSOAS:  {len(detections)}", _GRAY, col_w * 2 + 20),
        ]
        for text, color, x in items:
            cv2.putText(img, text, (x, h - 18), self._font, 0.55, color, 1, cv2.LINE_AA)
        fps_text = f"{fps:.0f} fps"
        tw, _ = cv2.getTextSize(fps_text, self._font, 0.45, 1)[0]
        cv2.putText(img, fps_text, (w - tw - 14, h - 18), self._font, 0.45, _GRAY, 1, cv2.LINE_AA)
        for x in [col_w, col_w * 2]:
            cv2.line(img, (x, h - bar_h + 8), (x, h - 8), (60, 60, 60), 1)

    def _update_fps(self):
        now = time.perf_counter()
        self._fps_times.append(now)
        self._fps_times = [t for t in self._fps_times if now - t < 1.0]

    def _current_fps(self):
        return max(len(self._fps_times), 1)

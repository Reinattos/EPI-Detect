# core/zones.py — gerenciamento de zonas de segurança
import json
import pathlib

import cv2
import numpy as np

ZONES_FILE = pathlib.Path(__file__).parent.parent / "zones.json"

_DEFAULT_COLORS = [
    [250, 204, 21],   # amarelo
    [239, 68,  68],   # vermelho
    [34,  197, 94],   # verde
    [99,  102, 241],  # índigo
    [249, 115, 22],   # laranja
]


def load_zones() -> list:
    if not ZONES_FILE.exists():
        return []
    try:
        return json.loads(ZONES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_zones(zones: list) -> None:
    ZONES_FILE.write_text(
        json.dumps(zones, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def next_color(zones: list) -> list:
    used = len(zones)
    return _DEFAULT_COLORS[used % len(_DEFAULT_COLORS)]


def person_zone_violations(detection, zones: list, frame_w: int, frame_h: int) -> list:
    """
    Retorna zonas onde esta pessoa está presente e está faltando algum EPI requerido.
    Usa o ponto médio dos pés (bottom-center da bounding box) como posição da pessoa.
    """
    cx = (detection.x1 + detection.x2) // 2
    cy = detection.y2  # pés

    violations = []
    for zone in zones:
        if not zone.get("active", True):
            continue
        pts = np.array(
            [[p[0] * frame_w, p[1] * frame_h] for p in zone["points"]],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        if len(pts) < 3:
            continue
        if cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0:
            missing = []
            requires = zone.get("requires", [])
            if "vest" in requires and not detection.has_vest:
                missing.append("COLETE")
            if "helmet" in requires and not getattr(detection, "has_helmet", False):
                missing.append("CAPACETE")
            if missing:
                violations.append({**zone, "missing": missing})
    return violations


def draw_zones(img: np.ndarray, zones: list) -> None:
    """Desenha zonas com efeito 3D sutil sobre o frame."""
    h, w = img.shape[:2]

    for zone in zones:
        if not zone.get("active", True):
            continue
        raw_pts = zone.get("points", [])
        if len(raw_pts) < 3:
            continue

        pts = np.array(
            [[int(p[0] * w), int(p[1] * h)] for p in raw_pts],
            dtype=np.int32,
        )

        r, g, b = zone.get("color", [250, 204, 21])
        color_bgr = (int(b), int(g), int(r))

        # — Sombra 3D (offset +4px, preto semi-transparente)
        shadow = pts + np.array([4, 4], dtype=np.int32)
        overlay_s = img.copy()
        cv2.fillPoly(overlay_s, [shadow], (0, 0, 0))
        cv2.addWeighted(overlay_s, 0.28, img, 0.72, 0, img)

        # — Preenchimento semi-transparente
        overlay_f = img.copy()
        cv2.fillPoly(overlay_f, [pts], color_bgr)
        cv2.addWeighted(overlay_f, 0.15, img, 0.85, 0, img)

        # — Borda interna (mais escura = profundidade)
        dim = tuple(max(0, int(c * 0.45)) for c in color_bgr)
        cv2.polylines(img, [pts], True, dim, 5, cv2.LINE_AA)
        # — Borda principal brilhante
        cv2.polylines(img, [pts], True, color_bgr, 2, cv2.LINE_AA)
        # — Highlight top-left das arestas (luz artificial)
        cv2.polylines(img, [pts], True, tuple(min(255, int(c * 1.5)) for c in color_bgr), 1, cv2.LINE_AA)

        # — Label centrado
        cx = int(np.mean(pts[:, 0]))
        cy = int(np.mean(pts[:, 1]))
        name = zone.get("name", "ZONA")
        requires = zone.get("requires", [])
        req_icons = []
        if "vest" in requires:
            req_icons.append("COLETE")
        if "helmet" in requires:
            req_icons.append("CAPACETE")

        font = cv2.FONT_HERSHEY_DUPLEX
        label_lines = [name] + ([" + ".join(req_icons)] if req_icons else [])
        for i, line in enumerate(label_lines):
            tw, th = cv2.getTextSize(line, font, 0.42, 1)[0]
            lx = cx - tw // 2
            ly = cy - 4 + i * 16
            # sombra texto
            cv2.putText(img, line, (lx + 1, ly + 1), font, 0.42, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(img, line, (lx, ly), font, 0.42, color_bgr, 1, cv2.LINE_AA)

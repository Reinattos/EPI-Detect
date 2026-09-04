"""
Rastreamento entre frames e estabilizacao temporal do veredito.

Duas responsabilidades:

1. Manter a mesma identidade para a mesma pessoa ao longo dos frames,
   por sobreposicao de caixa (IoU).

2. Estabilizar o veredito de cada EPI por voto de maioria numa janela
   de frames. Sem isso o rotulo pisca: uma pessoa andando cruza sombra,
   vira de lado e a cobertura de cor oscila em torno do limite. O voto
   troca o resultado apenas quando a mudanca persiste.

A janela tambem alimenta o contador de duracao da violacao, que e mais
util num painel de seguranca do que o estado instantaneo.
"""

from __future__ import annotations

from collections import deque

import config


def iou(a, b) -> float:
    """Intersecao sobre uniao de duas caixas (x1, y1, x2, y2)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter = (max(0, min(ax2, bx2) - max(ax1, bx1)) *
             max(0, min(ay2, by2) - max(ay1, by1)))
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


class Track:
    """Historico de uma pessoa entre frames."""

    __slots__ = ("id", "box", "vest", "helmet", "missing", "violation_frames")

    def __init__(self, track_id: int, box):
        self.id = track_id
        self.box = box
        self.vest = deque(maxlen=config.STABILIZE_WINDOW)
        self.helmet = deque(maxlen=config.STABILIZE_WINDOW)
        self.missing = 0
        self.violation_frames = 0

    def vote(self, has_vest: bool, has_helmet: bool) -> tuple[bool, bool]:
        """Adiciona a leitura do frame e devolve o veredito estabilizado."""
        self.vest.append(has_vest)
        self.helmet.append(has_helmet)
        ratio = config.STABILIZE_RATIO
        vest = sum(self.vest) > len(self.vest) * ratio
        helmet = sum(self.helmet) > len(self.helmet) * ratio
        self.violation_frames = 0 if (vest and helmet) else self.violation_frames + 1
        return vest, helmet


class Tracker:
    """Associa deteccoes a tracks e estabiliza os vereditos."""

    def __init__(self):
        self._tracks: dict[int, Track] = {}
        self._next_id = 0

    def update(self, detections, fps: float = 24.0):
        """Anota cada deteccao com track_id, veredito estavel e duracao.

        Modifica as deteccoes no lugar e devolve a mesma lista, para o
        chamador poder seguir usando os objetos que ja tinha.
        """
        assigned: dict[int, object] = {}
        used: set[int] = set()

        for det in detections:
            best_iou, best_id = 0.0, None
            for track_id, track in self._tracks.items():
                if track_id in used:
                    continue
                score = iou(det.box, track.box)
                if score > best_iou:
                    best_iou, best_id = score, track_id

            if best_id is not None and best_iou > config.TRACK_IOU:
                track = self._tracks[best_id]
                used.add(best_id)
            else:
                track = Track(self._next_id, det.box)
                self._tracks[self._next_id] = track
                used.add(self._next_id)
                self._next_id += 1

            track.box = det.box
            track.missing = 0
            det.has_vest, det.has_helmet = track.vote(det.has_vest, det.has_helmet)
            det.track_id = track.id
            det.violation_frames = track.violation_frames
            assigned[track.id] = det

        # tracks sem correspondencia envelhecem e saem depois de um tempo,
        # o que tolera oclusao curta sem trocar a identidade da pessoa
        for track_id in list(self._tracks):
            if track_id not in assigned:
                self._tracks[track_id].missing += 1
                if self._tracks[track_id].missing > config.TRACK_MAX_MISSING:
                    del self._tracks[track_id]

        return detections

    def violation_seconds(self, det, fps: float) -> float:
        """Ha quantos segundos esta pessoa esta fora de conformidade."""
        return det.violation_frames / max(fps, 1.0)


def summarize(detections) -> dict[str, int]:
    """Conta o quadro atual para o painel.

    Colete e capacete sao contados em separado porque a violacao parcial
    (com colete, sem capacete) e o caso mais comum na pratica e sumiria
    num unico contador de conformes.
    """
    counts = {"ok": 0, "no_vest": 0, "no_helmet": 0, "total": 0}
    for det in detections:
        counts["total"] += 1
        if not det.has_vest:
            counts["no_vest"] += 1
        if not det.has_helmet:
            counts["no_helmet"] += 1
        if det.compliant:
            counts["ok"] += 1
    return counts

"""
Testes de rastreamento e estabilizacao temporal.

A estabilizacao existe porque a cobertura de cor oscila em torno do
limite quando a pessoa cruza sombra ou vira de lado. O voto de maioria
so deve trocar o veredito quando a mudanca persiste.
"""

import config
from core.detector import Detection
from core.tracker import Tracker, iou, summarize


def make(box, vest=True, helmet=True, conf=0.9):
    return Detection(box=box, confidence=conf, has_vest=vest, has_helmet=helmet)


def test_iou_identico_e_um():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_iou_disjunto_e_zero():
    assert iou((0, 0, 10, 10), (50, 50, 60, 60)) == 0.0


def test_mesma_pessoa_mantem_o_id_entre_frames():
    tracker = Tracker()
    first = tracker.update([make((100, 100, 150, 300))])[0]
    # pequeno deslocamento, como alguem andando
    second = tracker.update([make((104, 100, 154, 300))])[0]
    assert first.track_id == second.track_id


def test_pessoa_distante_recebe_id_novo():
    tracker = Tracker()
    a = tracker.update([make((100, 100, 150, 300))])[0]
    b = tracker.update([make((600, 100, 650, 300))])[0]
    assert a.track_id != b.track_id


def test_leitura_isolada_nao_troca_o_veredito():
    """Um unico frame divergente nao deve mudar o rotulo."""
    tracker = Tracker()
    box = (100, 100, 150, 300)
    for _ in range(config.STABILIZE_WINDOW):
        tracker.update([make(box, helmet=True)])
    # um frame perde o capacete: a maioria da janela ainda diz que tem
    result = tracker.update([make(box, helmet=False)])[0]
    assert result.has_helmet, "falha isolada nao deveria derrubar o veredito"


def test_mudanca_persistente_troca_o_veredito():
    tracker = Tracker()
    box = (100, 100, 150, 300)
    for _ in range(config.STABILIZE_WINDOW):
        tracker.update([make(box, helmet=True)])
    for _ in range(config.STABILIZE_WINDOW):
        result = tracker.update([make(box, helmet=False)])[0]
    assert not result.has_helmet, "mudanca sustentada deveria trocar o veredito"


def test_duracao_da_violacao_acumula():
    tracker = Tracker()
    box = (100, 100, 150, 300)
    for _ in range(config.STABILIZE_WINDOW * 2):
        result = tracker.update([make(box, vest=False, helmet=False)])[0]
    assert result.violation_frames > 0


def test_conformidade_exige_as_duas_pecas():
    assert make((0, 0, 1, 1), vest=True, helmet=True).compliant
    assert not make((0, 0, 1, 1), vest=True, helmet=False).compliant
    assert not make((0, 0, 1, 1), vest=False, helmet=True).compliant


def test_resumo_conta_violacao_parcial_em_separado():
    """Com colete e sem capacete e o caso mais comum na pratica."""
    counts = summarize([
        make((0, 0, 1, 1), vest=True, helmet=True),
        make((0, 0, 1, 1), vest=True, helmet=False),
        make((0, 0, 1, 1), vest=False, helmet=True),
    ])
    assert counts == {"ok": 1, "no_vest": 1, "no_helmet": 1, "total": 3}

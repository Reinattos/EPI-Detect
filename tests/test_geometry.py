"""
Testes da geometria de analise.

O foco e garantir que os recortes de colete e capacete caiam onde
devem, porque foi justamente ai que a implementacao errou durante o
desenvolvimento: recorte fixo por percentual da caixa media o piso do
galpao em pessoas de perfil, e derivar a escala da cabeca pela largura
colapsava o recorte para poucos pixels de altura.
"""

import config
from core.detector import head_geometry, helmet_roi, vest_roi

# pose sintetica de uma pessoa em pe, de frente, caixa (100, 50)-(180, 300)
BOX = (100, 50, 180, 300)
POSE = [
    (140.0, 70.0, 0.9),    # 0 nariz
    (135.0, 65.0, 0.9),    # 1 olho esq
    (145.0, 65.0, 0.9),    # 2 olho dir
    (130.0, 68.0, 0.8),    # 3 orelha esq
    (150.0, 68.0, 0.8),    # 4 orelha dir
    (120.0, 100.0, 0.95),  # 5 ombro esq
    (160.0, 100.0, 0.95),  # 6 ombro dir
    (115.0, 140.0, 0.9),   # 7 cotovelo esq
    (165.0, 140.0, 0.9),   # 8 cotovelo dir
    (110.0, 175.0, 0.85),  # 9 pulso esq
    (170.0, 175.0, 0.85),  # 10 pulso dir
    (125.0, 180.0, 0.9),   # 11 quadril esq
    (155.0, 180.0, 0.9),   # 12 quadril dir
    (125.0, 240.0, 0.85),  # 13 joelho esq
    (155.0, 240.0, 0.85),  # 14 joelho dir
    (125.0, 295.0, 0.8),   # 15 tornozelo esq
    (155.0, 295.0, 0.8),   # 16 tornozelo dir
]


def test_vest_roi_cobre_dos_ombros_a_bacia():
    x1, y1, x2, y2 = vest_roi(BOX, POSE, 640, 480)
    assert y1 < 100, "topo deve ficar na linha dos ombros ou acima"
    assert y2 > 180, "base deve alcancar a bacia"
    assert x1 < 120 and x2 > 160, "largura deve cobrir os dois ombros"


def test_helmet_roi_fica_acima_do_nariz():
    x1, y1, x2, y2 = helmet_roi(BOX, POSE, 640, 480)
    assert y1 == 50, "topo do recorte e o topo da caixa"
    assert y2 < 70, "base fica acima do nariz (meio da cabeca)"
    assert y2 - y1 >= 4, "recorte nunca degenera em altura"


def test_helmet_roi_nao_degenera_em_pessoa_distante():
    """Cabeca pequena ainda precisa gerar recorte utilizavel."""
    small_box = (100, 50, 118, 100)
    small_pose = [(109.0, 56.0, 0.6)] + [(0.0, 0.0, 0.0)] * 4 + [
        (104.0, 62.0, 0.9), (114.0, 62.0, 0.9)] + [(0.0, 0.0, 0.0)] * 10
    x1, y1, x2, y2 = helmet_roi(small_box, small_pose, 640, 480)
    assert y2 - y1 >= 4
    assert x2 - x1 >= 4


def test_head_geometry_ignora_rosto_incoerente():
    """Nariz em posicao absurda nao deve arrastar o centro da cabeca.

    De perfil ou de costas o modelo estima keypoints faciais com
    confianca marginal em posicao errada; os ombros sao a ancora.
    """
    pose = list(POSE)
    pose[0] = (400.0, 70.0, 0.4)  # nariz muito longe do corpo
    pose[1] = (0.0, 0.0, 0.0)
    pose[2] = (0.0, 0.0, 0.0)
    pose[3] = (0.0, 0.0, 0.0)
    pose[4] = (0.0, 0.0, 0.0)
    cx, half_w, top, chin = head_geometry(BOX, pose)
    assert 110 < cx < 170, f"centro deveria seguir os ombros, veio {cx}"


def test_head_geometry_sem_keypoints_usa_a_caixa():
    cx, half_w, top, chin = head_geometry(BOX, None)
    assert cx == 140.0
    assert top == 50.0
    assert chin > top


def test_limites_de_config_sao_coerentes():
    """Os cortes calibrados devem manter separacao entre as classes."""
    assert 0 < config.VEST_THRESH < 1
    assert 0 < config.HELMET_THRESH < 1
    # medido em video real: com capacete >= 0.29, sem capacete = 0.00
    assert config.HELMET_THRESH < 0.29, "corte acima do minimo medido"
    assert config.MAX_ASPECT > 1.0, "pessoa sentada e mais larga que alta"

# config.py — EPI Vest Detector
# Ajuste aqui sem tocar no código principal

# --- Modelo ---
MODEL_NAME = "yolov8n-pose.pt"  # pose: detecta APENAS humanos + keypoints (filtra cones etc.)
INPUT_SIZE = 416  # menor custo em CPU; suficiente para webcam/CCTV proxima
CONF_THRESH = 0.20  # baixo para pegar pessoas no fundo
PERSON_CLASS = 0  # mantido para compatibilidade, ignorado pelo pose model

# Filtros anti-falso-positivo
KP_CONF_THRESH = 0.30  # confiança mínima de keypoint para usar coordenada
MIN_PERSON_HEIGHT = 35  # px mínimos — aceita pessoas distantes/menores
MIN_PERSON_RATIO = 0.35  # altura/largura mínima (cones têm ratio < isso)

# --- Análise de colete (HSV) ---
# Laranja high-vis  (EN ISO 20471 — H 5-22, alta saturação)
ORANGE_LOW = (5, 90, 60)
ORANGE_HIGH = (22, 255, 255)
# Amarelo-limão / verde fluorescente (coletes padrão CCTV — H 25-92)
# S e V baixos porque câmera de segurança tem compressão e variação de luz
YELLOW_LOW = (25, 50, 50)
YELLOW_HIGH = (92, 255, 255)

# Torso: pescoço (22%) até quadril (78%) — região exata do colete
TORSO_TOP = 0.22
TORSO_BOTTOM = 0.78
# Coletes abertos e pessoas sentadas deixam pouca area fluorescente aparente.
# 3% ainda exige uma mancha relevante dentro do torso e reconhece esse cenario.
VEST_THRESH = 0.03
# Exige cor fluorescente nos dois lados do torso para rejeitar uma faixa solta
# colocada somente sobre um braco ou ombro.
VEST_SIDE_THRESH = 0.005

# --- Performance ---
FRAME_SKIP = 8  # detecta 1 a cada N frames; reaproveita o resultado entre inferencias
STREAM_FPS = 20  # FPS alvo do stream web (encoder thread)
DETECTION_INTERVAL = 0.20  # ate 5 analises/s; captura e stream nao aguardam a IA
TORCH_THREADS = 2  # reserva CPU para captura, JPEG e servidor web (maquina com 4 threads)
WEBCAM_WIDTH = 960
WEBCAM_HEIGHT = 540
WEBCAM_FPS = 30

# --- UI ---
COLOR_OK = (34, 197, 94)  # verde  (BGR invertido abaixo)
# OpenCV usa BGR. Este valor produz vermelho (RGB #ef4444), nao azul.
COLOR_WARN = (68, 68, 239)  # vermelho
COLOR_INFO = (250, 204, 21)  # amarelo
COLOR_BG = (15, 15, 15)  # fundo status bar
ALPHA_OVERLAY = 0.65  # opacidade dos painéis

# Fontes (Pillow) — caminho relativo ao projeto
FONT_PATH = None  # None = usa fonte embutida do Pillow
FONT_SIZE_LG = 22
FONT_SIZE_MD = 16
FONT_SIZE_SM = 13

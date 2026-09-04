# Arquitetura

## Fluxo por quadro

```
   quadro
     │
     ▼
┌─────────────────┐
│ YOLOv8-pose     │  caixa + 17 keypoints por pessoa
└────────┬────────┘  ~99% do custo por quadro
         │
         ▼
┌─────────────────┐
│ filtros         │  proporção (reflexo de piso)
│                 │  coerência da pose (detecção fantasma)
│                 │  coincidência facial (caixa duplicada)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ recortes        │  vest_roi:   ombros → bacia
│ (keypoints)     │  helmet_roi: crânio → meio da cabeça
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ análise         │  colete:   cobertura HSV
│ (~5 ms total)   │  capacete: forma + uniformidade em elipse
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ tracker         │  identidade por IoU
│                 │  voto de maioria na janela
│                 │  duração da violação
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ overlay         │  esqueleto por zona, rótulos, painel
└────────┬────────┘
         │
         ▼
   quadro anotado
```

## Módulos

### `core/detector.py`

Concentra a decisão de EPI. A função `detect()` devolve uma lista de
`Detection`, cada uma com o veredito de colete e capacete, a confiança e
os recortes usados na análise.

`head_geometry()` merece atenção: é a função que localiza a cabeça, e a
ordem de prioridade das fontes não é arbitrária. Ombros primeiro
(confiança 0.9+), keypoints faciais só como refinamento validado. A
escala vertical vem da distância topo-da-caixa até o ombro.

### `core/tracker.py`

Mantém identidade entre quadros e estabiliza o veredito. Separado do
detector de propósito: o detector é sem estado, o tracker é o único lugar
que acumula histórico. Isso mantém o detector testável quadro a quadro.

### `core/overlay.py`

Só desenho, nenhuma decisão. Recebe as detecções já resolvidas.

A função `make_canvas()` amplia a tela para colocar o painel **ao lado**
do vídeo em vez de sobre ele. Sobrepor custava os 235 px da direita da
imagem, e é justamente nessa faixa que costuma cair marca de água ou
relógio de câmera.

### `core/capture.py`

Leitura em thread separada, com descarte de quadros antigos. Necessário
para RTSP: se a leitura fosse síncrona, o buffer da câmera acumularia e a
latência cresceria sem parar.

### `core/zones.py`

Zonas de risco como polígonos em coordenadas normalizadas (0.0 a 1.0),
então funcionam em qualquer resolução de câmera.

## Decisões de projeto

### Por que pose, e não um detector treinado de EPI

Um detector treinado especificamente para colete e capacete daria
precisão maior. O custo é o dataset: milhares de imagens anotadas do
ambiente real, e reanotação quando o EPI ou a iluminação mudam.

Usando pose, a única coisa que precisa de calibração são as faixas de cor
e os limites de cobertura, ajustáveis em minutos. Para um ambiente
específico e com volume, treinar um modelo dedicado é o caminho correto —
está registrado nas limitações do README.

### Por que o detector é sem estado

`EPIDetector.detect()` não guarda histórico. Todo acúmulo fica no
`Tracker`. Isso permite testar a decisão de um quadro isolado e torna
possível compartilhar um único detector entre várias câmeras.

### Por que a resolução é escolhida em tempo de execução

Porque não existe valor bom para todo caso, e a diferença é grande: em
plano fechado, 768 acerta mais que 1280 e roda três vezes mais rápido; em
plano aberto, 1280 é obrigatório ou pessoas ao fundo desaparecem. Medir
o tamanho das pessoas em três quadros de amostra custa menos de um
segundo e evita errar nas duas pontas.

## Migrando da v1

Se você usava a versão anterior
([Reinattos/EPI-Detect](https://github.com/Reinattos/EPI-Detect)), o que
muda na prática:

### Configuração

Os nomes de alguns parâmetros mudaram, e os limites foram recalibrados.
Não copie o `config.py` antigo por cima — em vez disso, coloque apenas os
seus ajustes num `settings_local.json`:

| v1 | v2 |
|---|---|
| `WEBCAM_INDEX` | `SOURCE` (aceita índice, arquivo ou RTSP) |
| `WEBCAM_WIDTH` / `WEBCAM_HEIGHT` | `FRAME_WIDTH` / `FRAME_HEIGHT` |
| `WEBCAM_FPS` | `TARGET_FPS` |
| `INPUT_SIZE` | `INPUT_SIZE` + `INPUT_SIZE_NEAR` |
| `VEST_SIDE_THRESH` | removido (a validação lateral saiu junto com o recorte por percentual) |
| `FRAME_SKIP` | removido (a taxa é limitada por `STREAM_FPS`) |

### Código

Se você importava do projeto:

| v1 | v2 |
|---|---|
| `from core.display import Renderer` | `from core.overlay import draw_detections, draw_sidebar, ...` |
| `Renderer().render(frame, dets, zones)` | `make_canvas()` + as funções de desenho |
| `detector.detect()` já estabilizava | `EPIDetector.detect()` + `Tracker.update()` |

O detector agora é sem estado. Se você dependia da estabilização embutida,
passe as detecções pelo `Tracker`:

```python
from core.detector import EPIDetector
from core.tracker import Tracker, summarize

detector = EPIDetector()
tracker = Tracker()

detections = tracker.update(detector.detect(frame))
counts = summarize(detections)
```

### Licença

A v1 declarava MIT, o que era incompatível com a dependência de
Ultralytics YOLOv8 (AGPL-3.0). Se você distribuiu algo derivado da v1 sob
MIT, vale revisar.

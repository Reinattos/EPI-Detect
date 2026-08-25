# EPI Detect

Visao computacional em tempo real para monitoramento de coletes de seguranca. O EPI Detect identifica pessoas com YOLO Pose, analisa a regiao do torso e publica o resultado em um dashboard web fluido.

> Status: prototipo funcional. O classificador de colete ainda usa regras de cor HSV e nao deve ser tratado como mecanismo unico de seguranca.

## Funcionalidades

- webcam, arquivo de video ou video demonstrativo;
- deteccao de pessoas e keypoints com YOLO;
- verificacao de cores fluorescentes laranja e amarelo-limao;
- evidencia bilateral para rejeitar colete colocado somente em um braco;
- estabilizacao temporal para reduzir oscilacoes de classificacao;
- pipeline assincrono: captura, inferencia e stream nao bloqueiam entre si;
- dashboard web com stream MJPEG, contadores, alertas e FPS;
- modo desktop opcional e exportacao de video processado.

## Requisitos e instalacao

- Python 3.10 ou superior;
- webcam opcional;
- CPU compativel; GPU nao e obrigatoria.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

python -m pip install -r requirements.txt
```

Na primeira execucao, a Ultralytics pode baixar automaticamente o peso oficial configurado em `MODEL_NAME`. Pesos `.pt` locais nao sao versionados.

## Execucao

```bash
# Dashboard com webcam
python server.py --source webcam

# Dashboard com demonstracao
python server.py --source demo

# Outro video ou camera
python server.py --source caminho/video.mp4
python server.py --source 1
```

Abra `http://localhost:5000`. No Windows, `iniciar.bat` oferece um menu equivalente.

Por seguranca, o servidor escuta apenas em `127.0.0.1`. Use `--host` somente quando souber como proteger o acesso de rede. Para automacao, `--no-browser` impede a abertura do navegador.

Modo desktop:

```bash
python detect.py --source webcam
python detect.py --source demo --save resultado.mp4
```

## Arquitetura

```text
camera/video -> captura do frame mais recente
                    |                  |
                    v                  v
             YOLO Pose + HSV      render + JPEG
                    |                  |
                    +---- estado ------+--> Flask/MJPEG
```

Os fluxos sao independentes. A webcam pode permanecer fluida mesmo quando a inferencia opera em uma frequencia menor. Consulte `PROJECT_CONTEXT.md` para o handoff tecnico completo e `CONTRIBUTING.md` antes de enviar alteracoes.

## API para o front-end

### `GET /video_feed`

Stream MJPEG (`multipart/x-mixed-replace`):

```html
<img src="/video_feed" alt="Camera monitorada">
```

### `GET /stats`

```json
{
  "with_vest": 1,
  "without_vest": 0,
  "total": 1,
  "fps": 20,
  "det_fps": 5,
  "alert": false,
  "status": "running",
  "error": null
}
```

### `GET /health`

Informa disponibilidade da camera e do modelo. Consulte `docs/API.md` para o contrato completo.

O front-end pode ser substituido sem alterar o pipeline, desde que preserve esses contratos ou atualize o servidor e a documentacao em conjunto.

## Configuracao

Os ajustes ficam em `config.py`:

- `INPUT_SIZE`: resolucao usada pela IA;
- `DETECTION_INTERVAL`: intervalo entre inferencias;
- `STREAM_FPS`: FPS alvo do dashboard;
- `TORCH_THREADS`: threads reservadas ao PyTorch;
- `VEST_THRESH`: cobertura fluorescente minima total;
- `VEST_SIDE_THRESH`: cobertura minima em cada lado do torso;
- faixas `ORANGE_*` e `YELLOW_*`: limites HSV.

## Dataset futuro

As imagens locais ficam em `dataset_epi/raw/`, separadas em `com_epi`, `sem_epi`, `uso_incorreto` e `falsos_positivos`. Esse conteudo e ignorado pelo Git para evitar publicar imagens de pessoas.

## Estrutura do projeto

```text
EPI-Detect/
├── core/                 # captura, detector e overlays
├── templates/            # dashboard web atual
├── dataset_epi/raw/      # imagens locais ignoradas pelo Git
├── models/               # modelos opcionais
├── server.py             # servidor e pipeline assincrono
├── detect.py             # modo desktop
├── config.py             # configuracao central
├── PROJECT_CONTEXT.md    # handoff tecnico e contexto para IAs
└── CONTRIBUTING.md       # guia para contribuidores
```

## Como contribuir

Issues e pull requests sao bem-vindos. Leia `CONTRIBUTING.md` antes de alterar o codigo e use os modelos de issue para fornecer ambiente, reproducao e impacto em desempenho. Vulnerabilidades devem seguir `SECURITY.md`.

## Privacidade e seguranca

- nao adicione imagens de pessoas ao repositorio;
- nao versione `.env`, credenciais, tokens ou caminhos locais;
- confirme autorizacao e politica de retencao antes de capturar imagens;
- revise pesos e videos antes de publica-los;
- use o sistema como apoio, nao como decisor unico de seguranca.

## Teste rapido

```bash
ruff check .
ruff format --check .
pytest
```

Depois, execute a webcam e confirme `/video_feed` e `/stats`.

## Licenca

O codigo original deste repositorio usa a licenca MIT, descrita em `LICENSE`. Dependencias, pesos e datasets de terceiros permanecem sujeitos as respectivas licencas e devem ser revisados antes da distribuicao.

# Contexto tecnico e handoff

Referencia para desenvolvedores e agentes de IA que forem alterar o EPI Detect. Leia tambem `README.md`, `CONTRIBUTING.md` e `config.py` antes de modificar o comportamento.

## Objetivo atual

Detectar pessoas em webcam ou video e classificar se um colete de seguranca esta vestido corretamente, mantendo o dashboard fluido em computadores sem GPU dedicada.

O repositorio e uma demonstracao tecnica e de portfolio. Nao ha dataset validado em escala, metricas de campo ou certificacao para uso como controle de seguranca.

## Estado da solucao

O sistema possui duas etapas:

1. `yolov8n-pose.pt` detecta pessoas e keypoints.
2. `core/detector.py` recorta o torso e procura cores fluorescentes em HSV.

Uma pessoa recebe `has_vest=True` quando:

- a cobertura total supera `VEST_THRESH`;
- os lados esquerdo e direito superam `VEST_SIDE_THRESH`;
- a maioria temporal das ultimas analises da mesma pessoa confirma o resultado.

Essa abordagem resolve o prototipo, mas nao reconhece semanticamente o formato do colete. O proximo salto de qualidade e um classificador leve treinado com recortes reais de torso.

## Pipeline concorrente

`server.py` mantem estado compartilhado protegido por lock:

- `_capture_loop`: atualiza `raw_frame` sem esperar a IA;
- `_detect_loop`: analisa somente o frame mais recente;
- `_encode_loop`: renderiza e codifica JPEG no FPS configurado;
- Flask: entrega pagina, MJPEG e estatisticas.

Nao volte a executar inferencia dentro do loop de renderizacao. Isso reintroduz travamentos visiveis.

## Mapa de arquivos

- `server.py`: Flask, concorrencia, estado e rotas;
- `detect.py`: aplicacao desktop alternativa;
- `config.py`: modelo, desempenho, HSV e UI;
- `core/capture.py`: captura e reconexao;
- `core/detector.py`: YOLO Pose e classificacao do torso;
- `core/display.py`: overlays OpenCV;
- `templates/index.html`: front-end atual;
- `dataset_epi/raw/`: imagens locais, nunca versionadas;
- `models/`: pesos opcionais;
- `demo/`: video demonstrativo opcional.

## Contrato do front-end

O front-end atual nao possui build step. Flask renderiza `templates/index.html`.

- `GET /`: pagina principal;
- `GET /video_feed`: MJPEG continuo;
- `GET /stats`: JSON com `with_vest`, `without_vest`, `total`, `fps`, `det_fps` e `alert`.
- `GET /health`: saude da camera, modelo e pipeline.

Ao redesenhar a interface:

- preserve os IDs usados pelo JavaScript ou substitua o script junto;
- mantenha `object-fit: contain` para nao distorcer os boxes;
- use verde para EPI correto e vermelho para ausencia/uso incorreto;
- nao trate `vest_coverage` como confianca percentual;
- mantenha layout responsivo e um estado de carregamento do modelo.

## Convencoes importantes

- OpenCV usa BGR, nao RGB. Vermelho `#ef4444` equivale a `(68, 68, 239)`.
- Nunca bloqueie captura ou encoder aguardando inferencia.
- Resultados da IA podem ser reutilizados entre frames visuais.
- Teste thresholds com positivo correto, sem EPI e uso incorreto.
- Nao adicione nomes, e-mails, empresas, caminhos de usuario ou credenciais.
- Nao envie imagens coletadas para GitHub.

## Desempenho de referencia

Na maquina usada durante o desenvolvimento, com quatro processadores logicos:

- webcam: 960x540;
- entrada YOLO: 416;
- stream: aproximadamente 18-20 FPS;
- inferencia: aproximadamente 3-5 analises por segundo;
- PyTorch: duas threads.

Esses numeros sao referencia, nao garantia. Meça `/stats` depois de alteracoes.

## Validacao minima

1. Execute `python -m py_compile server.py detect.py config.py core/*.py`.
2. Inicie `python server.py --source webcam`.
3. Confirme que `/video_feed` abre antes ou durante o carregamento do modelo.
4. Confirme que `/stats` permanece responsivo.
5. Teste colete correto, sem colete e colete em apenas um braco.
6. Observe estabilidade durante movimento.

## Roadmap recomendado

1. Coletar e revisar dataset balanceado.
2. Extrair recortes de torso usando os keypoints existentes.
3. Treinar classificador para `com_epi`, `sem_epi` e `uso_incorreto`.
4. Manter HSV como evidencia auxiliar ou fallback.
5. Exportar para ONNX/OpenVINO e medir latencia.
6. Criar testes com videos fixos e metricas de falsos positivos/negativos.

## Fora de escopo atual

- autenticacao e usuarios;
- banco de dados e historico persistente;
- notificacoes externas;
- decisao automatica de conformidade legal;
- garantia de seguranca ou precisao de 100%.

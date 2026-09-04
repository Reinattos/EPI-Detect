# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [2.0.0] — 2026-09

Reescrita do núcleo de detecção. A mudança que motiva a virada de versão
maior é a **detecção de capacete**, que não existia na v1, mas o caminho
até ela obrigou a repensar como as regiões de análise são delimitadas.

### Adicionado

#### Detecção de capacete

A v1 monitorava apenas colete. Agora cada pessoa é avaliada em duas peças
independentes, o que expõe a **violação parcial** — alguém de colete que
subiu na empilhadeira sem capacete. Esse é o caso mais comum na prática e
desaparecia num contador único de conformes.

Casar capacete por cor não funciona: eles existem em laranja, amarelo,
branco, azul e vermelho, e qualquer boné da mesma cor viraria falso
positivo. O que discrimina é a combinação de superfície lisa (plástico tem
desvio padrão de brilho baixo, cabelo é texturizado), exclusão de pele e
cabelo, e cobertura da calota dentro de máscara elíptica.

#### Recortes de análise ancorados em pose

Na v1 a faixa do tronco vinha de percentuais fixos da caixa. Agora os
keypoints delimitam as regiões:

| Peça | Região | Keypoints |
|---|---|---|
| Colete | ombros até a bacia | 5, 6, 11, 12 |
| Capacete | crânio até o meio da cabeça | derivado dos ombros |

O recorte por percentual fixo acabava medindo o piso do galpão em pessoas
de perfil, e o efeito era um veredito baseado em pixels de concreto.

#### Esqueleto colorido por zona de equipamento

O esqueleto não é colorido por pessoa, e sim por peça de EPI: tronco e
braços seguem o colete, cabeça e face seguem o capacete, pernas ficam
neutras por não serem monitoradas. Isso torna a violação parcial legível
sem depender de texto — tronco verde com cabeça vermelha diz "tem colete,
falta capacete" numa olhada.

#### Rastreamento com identidade e duração

A v1 tinha estabilização temporal, mas sem identidade persistente. Agora
cada pessoa mantém um identificador entre quadros, e disso vem o contador
de **há quantos segundos** aquela pessoa está fora de conformidade — mais
útil num painel de segurança do que o estado instantâneo.

#### Seleção automática de resolução

Descoberta que mais afeta o desempenho: não existe um valor bom de
resolução para todo caso.

| Cena | Pessoas ocupam | Resolução | Observação |
|---|---|---|---|
| Plano aberto | ~20% da altura | 1280 | Em 896, duas pessoas desaparecem |
| Plano fechado | ~60% da altura | 768 | Acerta **mais** que 1280 e roda 3x mais rápido |

O `render.py` mede o tamanho das pessoas em três quadros de amostra e
decide. Em vídeo de plano fechado isso levou o processamento de 165s para
55s, com detecção melhor.

#### Novo entrypoint `render.py`

Processa arquivo de vídeo e grava MP4 anotado, com opções de recorte
(`--crop-top`, `--crop-bottom`) para remover relógio ou marca gravada no
material de origem, e `--camera-name` para identificar a câmera ao juntar
clipes.

#### Testes e integração contínua

15 testes cobrindo a geometria dos recortes e o comportamento do
rastreador, incluindo os casos que a implementação errou durante o
desenvolvimento: recorte degenerado em pessoa distante, keypoint facial
incoerente, e leitura isolada que não deve derrubar o veredito. Workflow
de CI rodando lint e testes em Python 3.10 e 3.12.

### Corrigido

#### Falso positivo de capacete por fundo claro

Medindo num retângulo em volta da cabeça, o teto claro do galpão entrava
na conta e disparava a regra de capacete branco. Uma cabeça descoberta
pontuava 0.595 — acima de qualquer limite razoável. A máscara elíptica
restringe a medição à calota e o mesmo caso passou a pontuar 0.000.

#### Recorte da cabeça caindo fora da cabeça

O nariz e os olhos parecem a âncora natural para localizar a cabeça, mas
de perfil ou de costas o modelo os estima em posição errada com confiança
apenas marginal. O recorte saía da cabeça e caía no piso: o HSV médio
dentro dele era cinza dessaturado, e a cobertura era zero antes de
qualquer filtro.

A cabeça passou a ser derivada dos **ombros**, que chegam com confiança
acima de 0.9 de forma consistente. Os pontos do rosto entram apenas como
refinamento, aceito só quando é coerente com essa estimativa.

#### Escala vertical da cabeça

Uma tentativa intermediária derivava a altura da cabeça da sua largura.
Quando a estimativa de largura errava, o recorte colapsava para 1 ou 2
pixels de altura e a análise não tinha pixels para decidir. A escala passou
a vir da distância **topo da caixa até o ombro**, que é medida direta.

#### Caixas duplicadas na mesma pessoa

Em plano fechado o detector às vezes devolve duas caixas para o mesmo
operador. Descartar por sobreposição não resolve: duas caixas grandes e
deslocadas ficam em IoU próximo de 0.44, abaixo de qualquer corte
razoável. Passou a usar coincidência dos pontos faciais — se dois rostos
estão no mesmo lugar, é a mesma pessoa.

#### Reflexo de piso detectado como pessoa

Com confiança baixa, reflexos no piso polido chegavam como caixas
achatadas em proporções de 6:1. Filtro de proporção descarta, já que
pessoa é sempre mais alta que larga, mesmo sentada.

#### Cobertura de colete subestimada

Material refletivo estoura a saturação de forma irregular sob luz
fluorescente, criando buracos na máscara de cor. Operação morfológica de
fechamento corrige.

#### Rótulo de EPI presente exibido em vermelho

A caixa fica vermelha quando falta qualquer peça, e os rótulos herdavam
essa cor — então "COLETE OK" aparecia em vermelho e lia como falha. Cada
peça passou a ter cor própria.

### Alterado

#### Licença: MIT para AGPL-3.0

**Correção importante para quem usa a v1.** O projeto depende de
Ultralytics YOLOv8, licenciado sob AGPL-3.0, que é uma licença viral —
trabalhos derivados precisam manter a mesma licença. A v1 declarava MIT,
o que é incompatível.

Se você pretende usar este código num produto de código fechado, precisa
de licença comercial da Ultralytics. Isso valia igualmente para a v1; a
mudança apenas torna a situação explícita.

#### Painel ao lado do vídeo, não sobre ele

O painel sobreposto custava 235 px da direita da imagem — faixa onde
costuma cair marca de água ou relógio de câmera. A tela agora é ampliada
e o quadro original aparece íntegro.

#### Nada é desenhado sobre o rosto

Uma versão intermediária marcava cabeça descoberta com uma retícula
centrada nela, o que cobria exatamente o que o operador de câmera precisa
ver. A marca de capacete ausente virou um arco acima da cabeça.

#### Espessura proporcional ao tamanho da pessoa

Linha de espessura fixa vira borrão em plano fechado e desaparece em plano
aberto. Agora acompanha a altura da caixa.

#### Detector sem estado, histórico isolado no rastreador

`EPIDetector.detect()` não guarda histórico; todo acúmulo fica no
`Tracker`. Isso permite testar a decisão de um quadro isolado e
compartilhar um único detector entre várias câmeras.

#### Configuração local fora do repositório

Ajustes de máquina vão em `settings_local.json`, ignorado pelo git, em vez
de editar `config.py`. Atualizar o projeto não sobrescreve mais o ajuste
local.

#### Limites com a medição que os justifica

Cada valor em `config.py` traz em comentário o dado que o sustenta. O
limite de capacete em 0.24, por exemplo: em vídeo real, cabeça com
capacete pontua entre 0.29 e 0.82; cabeça descoberta pontua 0.00.

### Removido

- `core/display.py`, substituído por `core/overlay.py`, que só desenha e
  não toma decisão.
- Identidade visual e configuração específicas de uma empresa. O projeto
  agora sobe genérico.
- Duas implementações paralelas de detecção que conviviam no código.
  Todos os entrypoints usam a mesma base.

### Desempenho

Medido em CPU, sem placa dedicada, vídeo 1280×720:

| Resolução | Tempo por quadro | Taxa |
|---|---|---|
| 640 | 159 ms | 6.0 /s |
| 768 | ~200 ms | 5.0 /s |
| 960 | 285 ms | 3.4 /s |
| 1280 | 519 ms | 1.9 /s |

O detector responde por cerca de 99% do custo por quadro. A análise de cor
de colete e capacete gasta 5 ms somados — otimizar essa parte não muda
nada, o que só ficou claro depois de medir.

---

## [1.0.0]

Primeira versão pública
([Reinattos/EPI-Detect](https://github.com/Reinattos/EPI-Detect)).

### Adicionado

- Detecção de pessoas com YOLO Pose.
- Identificação de colete refletivo por regras de cor HSV na região do
  tronco, com verificação de laranja e amarelo-limão.
- Validação bilateral para reduzir falso positivo.
- Estabilização temporal da classificação.
- Pipeline assíncrono de captura e inferência.
- Painel web com métricas e alertas.
- Registro de eventos com marcação de horário.
- API local para integração.
- Suporte a webcam, arquivo de vídeo e vídeo de demonstração.

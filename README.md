# EPI Detect

Detecção automática de colete refletivo e capacete de segurança em vídeo,
usando estimativa de pose para saber **onde** cada equipamento deveria estar.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-pose-00FFFF)](https://docs.ultralytics.com/)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)
[![CI](https://img.shields.io/badge/tests-15%20passing-brightgreen)](.github/workflows/ci.yml)

![Detecção em galpão logístico](docs/images/demo-armazem.gif)

Roda em **CPU comum**, sem placa de vídeo dedicada. Funciona com webcam,
arquivo de vídeo ou câmera IP via RTSP.

> ### Versão 2.0
>
> Reescrita do núcleo de detecção. O destaque é a **detecção de capacete**,
> que não existia na versão anterior — agora colete e capacete são avaliados
> de forma independente, o que expõe a violação parcial (de colete, sem
> capacete), que era invisível num contador único.
>
> Também entrou: recortes de análise delimitados por keypoints em vez de
> percentuais fixos da caixa, rastreamento com identidade e duração da
> violação, esqueleto colorido por zona de equipamento, e seleção automática
> de resolução — que em plano fechado deixou o processamento **3x mais
> rápido** e ainda mais preciso.
>
> A licença mudou de MIT para **AGPL-3.0**. Não é escolha estética: o
> Ultralytics YOLOv8 é AGPL-3.0 e a v1 declarava MIT, o que era
> incompatível. [Detalhes](#licença).
>
> O histórico completo, com os erros que precisaram ser corrigidos e a
> medição por trás de cada decisão, está no [CHANGELOG](CHANGELOG.md).
> Versão anterior: [Reinattos/EPI-Detect](https://github.com/Reinattos/EPI-Detect).

---

## Índice

- [O que mudou na v2](#o-que-mudou-na-v2)
- [O que ele faz](#o-que-ele-faz)
- [Instalação](#instalação)
- [Como usar](#como-usar)
- [Como funciona](#como-funciona)
- [Configuração](#configuração)
- [Desempenho](#desempenho)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Limitações](#limitações)
- [Licença](#licença)

---

## O que mudou na v2

| | v1 | v2 |
|---|---|---|
| **Capacete** | não detectava | forma e uniformidade em máscara elíptica |
| **Colete** | percentual fixo da caixa | ombros até a bacia, via keypoints |
| **Rastreamento** | estabilização sem identidade | identidade por pessoa + duração da violação |
| **Esqueleto** | não desenhado | colorido por zona de equipamento |
| **Resolução** | fixa | escolhida medindo o tamanho das pessoas |
| **Painel** | sobre o vídeo | ao lado, sem cobrir a imagem |
| **Testes** | — | 15 testes + CI |
| **Licença** | MIT (incompatível) | AGPL-3.0 |

Três correções valem destaque porque o caminho errado era o intuitivo:

**Falso positivo de capacete.** Medindo num retângulo em volta da cabeça, o
teto claro do galpão entrava na conta e uma cabeça descoberta pontuava
0.595 — acima de qualquer limite razoável. A máscara elíptica derrubou o
mesmo caso para 0.000.

**Recorte caindo fora da cabeça.** Ancorar no nariz e nos olhos parece
natural, mas de perfil o modelo os estima em posição errada com confiança
marginal, e o recorte ia para o piso. Os ombros, com confiança acima de
0.9, viraram a âncora.

**Caixa duplicada na mesma pessoa.** Descartar por sobreposição não
resolve: em plano fechado duas caixas sobre o mesmo operador ficam em IoU
próximo de 0.44. O sinal confiável é o rosto.

---

## O que ele faz

Para cada pessoa no quadro, o sistema responde duas perguntas de forma
independente: **está de colete?** e **está de capacete?**

Isso importa porque a violação mais comum na prática não é a pessoa sem
nenhum equipamento — é a violação **parcial**. Alguém de colete que subiu
na empilhadeira sem capacete. Um contador único de "conformes" esconde
esse caso; aqui ele aparece.

![Violação parcial: colete detectado, capacete ausente](docs/images/detail-violacao-parcial.png)

No quadro acima o operador está de colete (tronco verde) e sem capacete
(cabeça vermelha, arco tracejado marcando o equipamento ausente). O
esqueleto é colorido **por zona de equipamento**, não por pessoa, então dá
para ler o diagnóstico sem ler texto nenhum.

### Recursos

| | |
|---|---|
| **Colete refletivo** | Análise de cor na faixa do tronco, delimitada pelos ombros e pela bacia |
| **Capacete** | Análise de forma e uniformidade na calota da cabeça |
| **Rastreamento** | Cada pessoa mantém a mesma identidade entre quadros |
| **Estabilização** | Voto de maioria numa janela de quadros, para o rótulo não piscar |
| **Duração da violação** | Há quantos segundos aquela pessoa está fora de conformidade |
| **Painel ao vivo** | Contadores, taxa de conformidade e alerta |
| **Fontes de vídeo** | Webcam, arquivo local ou câmera IP (RTSP) |
| **Interface web** | Servidor Flask opcional, com zonas de risco desenháveis |

---

## Instalação

Você precisa de **Python 3.10 ou mais novo**. Nada além disso — o modelo é
baixado sozinho na primeira execução.

### 1. Baixe o projeto

```bash
git clone https://github.com/SEU-USUARIO/epi-detect.git
cd epi-detect
```

### 2. Crie um ambiente virtual

Isso mantém as bibliotecas deste projeto separadas do resto do sistema.

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux ou macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Rode

```bash
python detect.py
```

A janela abre com a imagem da sua webcam e as anotações em tempo real.
Pressione **Q** para sair.

> **A primeira execução demora.** O modelo (cerca de 7 MB) é baixado e o
> PyTorch compila os kernels. Em máquinas modestas isso pode levar alguns
> minutos. As execuções seguintes começam em segundos.

### Atalho para Windows: `iniciar.bat`

Quem não trabalha com linha de comando pode dar dois cliques em
**`iniciar.bat`**. Ele cria o ambiente virtual, instala as dependências na
primeira execução e abre um menu com as opções de uso.

Isso é uma decisão deliberada, e vale explicar o porquê: **o público desta
ferramenta não é só quem programa.** Um detector de EPI interessa a técnico
de segurança do trabalho, encarregado de operação e gestor de frota — gente
que precisa avaliar o resultado, não montar ambiente Python. Exigir
terminal exclui justamente quem mais se beneficiaria.

O `.bat` não substitui nada: a linha de comando está documentada acima e é
o caminho principal para quem for integrar ou modificar o projeto. Ele é
uma porta de entrada adicional, não um atalho para não documentar.

---

## Como usar

### Webcam

```bash
python detect.py
```

Se você tem mais de uma câmera, escolha pelo índice:

```bash
python detect.py --source 1
```

Atalhos com a janela aberta:

| Tecla | Ação |
|---|---|
| `Q` ou `Esc` | Encerra |
| `Z` | Liga e desliga as caixas tracejadas de análise |
| `Espaço` | Pausa |

### Arquivo de vídeo

```bash
python detect.py --source caminho/do/video.mp4
```

### Câmera IP (RTSP)

```bash
python detect.py --source "rtsp://usuario:senha@192.168.0.50:554/stream1"
```

A URL exata varia por fabricante. Consulte o manual do modelo ou o painel
de configuração da câmera.

### Gerar um vídeo anotado

Para processar um arquivo e salvar o resultado em MP4:

```bash
python render.py entrada.mp4
```

O arquivo sai como `entrada_epi.mp4` na mesma pasta. Para controlar melhor:

```bash
python render.py entrada.mp4 saida.mp4 --camera-name "CAM 02" --crop-top 96
```

Opções úteis do `render.py`:

| Opção | Para que serve |
|---|---|
| `--camera-name` | Rótulo no cabeçalho, útil ao juntar clipes de câmeras diferentes |
| `--imgsz N` | Fixa a resolução do modelo em vez de detectar automaticamente |
| `--crop-top N` | Corta pixels do topo, para remover relógio ou marca gravada |
| `--crop-bottom N` | Corta pixels da base |
| `--no-zones` | Oculta as caixas tracejadas de análise |
| `--clock-start` | Hora inicial exibida no cabeçalho |

### Interface web

```bash
python server.py
```

Abra `http://localhost:5000`. A interface web acrescenta o desenho de
**zonas de risco**: você delimita áreas do quadro onde determinado
equipamento é obrigatório, e a checagem passa a valer só ali.

---

## Como funciona

O ponto de partida é o **YOLOv8-pose**, que devolve, para cada pessoa, uma
caixa e 17 pontos do corpo (nariz, olhos, ombros, quadris, joelhos e assim
por diante).

A pose não serve apenas para desenhar o esqueleto na tela. Ela resolve o
problema central: **saber onde procurar cada equipamento**.

```
     ●  ← nariz, olhos, orelhas
   ╱─┴─╲    ┌─────────────────────┐
  ●     ●   │ zona do CAPACETE    │  topo do crânio até o
  │  │  │   │ análise de forma    │  meio da cabeça
  ●──┼──●   └─────────────────────┘
  │  │  │   ┌─────────────────────┐
  │  ●  │   │ zona do COLETE      │  ombros até a bacia
  ●─────●   │ análise de cor      │
  │     │   └─────────────────────┘
  ●     ●   ← não monitorado
```

### Colete: análise de cor

Colete refletivo tem cor característica (laranja ou amarelo de alta
visibilidade). Basta medir que fração da faixa do tronco cai nessa cor.

A parte não óbvia é que o material refletivo **estoura a saturação de forma
irregular** sob luz fluorescente de galpão, criando buracos na máscara de
cor. Sem uma operação morfológica de fechamento, a cobertura é subestimada.

### Capacete: forma e uniformidade

Aqui a cor sozinha não resolve. Capacete existe em laranja, amarelo,
branco, azul e vermelho — casar por cor daria falso positivo em qualquer
boné da mesma cor.

O que discrimina de verdade é a combinação de três sinais:

1. **Superfície lisa.** Plástico tem desvio padrão de brilho baixo; cabelo
   é texturizado.
2. **Não é pele nem cabelo.** Ambos são excluídos antes de pontuar.
3. **Cobre a calota.** A medição acontece dentro de uma máscara elíptica
   ajustada à cabeça.

A máscara elíptica não é detalhe estético. Medindo num retângulo, o teto
claro do galpão atrás da cabeça entrava na conta e gerava falso positivo
em cabeça descoberta — o efeito era um capacete branco inexistente.

### Como a cabeça é localizada

Esta foi a parte que mais deu trabalho, e vale registrar porque o caminho
errado é tentador.

A intuição diz: use os keypoints do rosto, que estão logo ali. O problema
é que **de perfil ou de costas o modelo estima nariz e olhos em posição
errada**, com confiança apenas marginal. Ancorar o recorte neles faz ele
sair da cabeça e cair no piso.

Os **ombros** chegam com confiança acima de 0.9 de forma consistente. Então
a cabeça é derivada deles, e os pontos do rosto entram só como refinamento,
aceito apenas quando é coerente com essa estimativa.

A escala vertical vem da distância **topo da caixa até o ombro**, que é uma
medida direta. Uma tentativa anterior derivava essa altura da largura da
cabeça; quando a estimativa de largura errava, o recorte colapsava para
poucos pixels de altura e a análise não tinha pixels suficientes para
decidir.

### Estabilização temporal

Uma pessoa andando cruza sombra, vira de lado, é parcialmente obstruída.
A cobertura de cor oscila em torno do limite e o rótulo pisca.

A solução é voto de maioria numa janela de quadros: o veredito só muda
quando a mudança **persiste**. A mesma janela alimenta o contador de
duração da violação, que é mais útil num painel de segurança do que o
estado instantâneo.

### Descartando detecções falsas

Duas verificações eliminam quase todo o ruído:

**Proporção.** Reflexo no piso de galpão chega ao detector como caixa
achatada, em proporções de 6:1. Pessoa é sempre mais alta que larga, mesmo
sentada, então o corte em 2.6 separa os dois casos com folga.

**Coerência da pose.** Pessoa real gera 10 ou mais keypoints confiáveis.
Detecção fantasma costuma trazer um ou dois.

Há ainda um terceiro caso, específico de plano fechado: o detector às
vezes devolve **duas caixas para a mesma pessoa**. O reflexo intuitivo é
descartar por sobreposição (IoU), mas duas caixas grandes e deslocadas
sobre o mesmo operador ficam em IoU próximo de 0.44 — abaixo de qualquer
corte razoável. O sinal confiável é o rosto: se os pontos faciais de duas
detecções coincidem, é a mesma pessoa.

---

## Configuração

Os limites em [`config.py`](config.py) foram calibrados medindo vídeo real,
não escolhidos por intuição. Cada valor tem um comentário registrando a
medição que o justifica.

| Parâmetro | Padrão | O que significa |
|---|---|---|
| `CONF_THRESH` | 0.20 | Confiança mínima do detector de pessoas |
| `VEST_THRESH` | 0.09 | Cobertura mínima de cor de colete no tronco |
| `HELMET_THRESH` | 0.24 | Cobertura mínima de capacete na calota |
| `MAX_ASPECT` | 2.60 | Proporção máxima largura/altura de uma pessoa |
| `MIN_KEYPOINTS` | 4 | Keypoints confiáveis mínimos para aceitar a detecção |
| `STABILIZE_WINDOW` | 6 | Tamanho da janela de voto de maioria |
| `INPUT_SIZE` | 1280 | Resolução do modelo em plano aberto |
| `INPUT_SIZE_NEAR` | 768 | Resolução do modelo em plano fechado |

Sobre o limite do capacete: em vídeo real, cabeça **com** capacete pontua
entre 0.29 e 0.82, enquanto cabeça **descoberta** pontua 0.00 depois de
excluir pele e cabelo. O corte em 0.24 fica confortavelmente entre os dois.

### Ajustando para a sua instalação

**Não edite `config.py`.** Crie um arquivo `settings_local.json` na raiz do
projeto com apenas as chaves que quiser mudar:

```json
{
  "SOURCE": "rtsp://usuario:senha@192.168.0.50:554/stream1",
  "HELMET_THRESH": 0.20,
  "SHOW_ANALYSIS_ZONES": false,
  "PORT": 8080
}
```

Esse arquivo é ignorado pelo git, então atualizar o projeto nunca sobrescreve
o seu ajuste local.

---

## Desempenho

Medido em CPU, sem placa de vídeo dedicada, em vídeo 1280×720:

| Resolução do modelo | Tempo por quadro | Taxa |
|---|---|---|
| 640 | 159 ms | 6.0 /s |
| 768 | ~200 ms | 5.0 /s |
| 960 | 285 ms | 3.4 /s |
| 1280 | 519 ms | 1.9 /s |

O detector responde por cerca de **99% do custo** por quadro. A análise de
cor de colete e capacete gasta 5 ms — otimizar essa parte não muda nada.

### Resolução: não existe um valor bom para todo caso

Este é o achado que mais afeta o desempenho na prática:

| Cena | Pessoas ocupam | Resolução correta | Por quê |
|---|---|---|---|
| Plano aberto (CFTV de galpão) | ~20% da altura | **1280** | Em 896, duas pessoas desaparecem |
| Plano fechado (cabine, portaria) | ~60% da altura | **768** | Acerta **mais** que 1280 e roda 3x mais rápido |

Por isso o `render.py` mede o tamanho das pessoas em três quadros de
amostra e escolhe sozinho. Você pode fixar com `--imgsz` quando quiser.

Para monitoramento de EPI, taxa alta não é necessária: ninguém tira o
capacete em 200 ms. Entre 4 e 6 quadros por segundo já capta qualquer
violação relevante.

### Acelerando

- **GPU NVIDIA:** instale o PyTorch com suporte CUDA e o ganho é automático.
- **iGPU Intel:** exporte para OpenVINO e ative pela variável de ambiente.

```bash
yolo export model=yolov8n-pose.pt format=openvino
export EPI_USE_OPENVINO=1
```

---

## Estrutura do projeto

```
epi-detect/
├── detect.py              Detecção ao vivo em janela (webcam, arquivo, RTSP)
├── render.py              Processa arquivo e grava MP4 anotado
├── server.py              Interface web com zonas de risco
├── config.py              Limites calibrados e configuração central
├── auto_config.py         Detecção de hardware e perfil sugerido
│
├── core/
│   ├── detector.py        Pose, recortes de análise e veredito de EPI
│   ├── tracker.py         Identidade entre quadros e estabilização
│   ├── overlay.py         Esqueleto, rótulos e painel
│   ├── capture.py         Leitura de vídeo em thread separada
│   └── zones.py           Zonas de risco poligonais
│
├── templates/index.html   Interface web
├── tests/                 Testes de geometria e rastreamento
├── docs/                  Documentação e imagens
└── demo/                  Vídeos de demonstração
```

### Demonstrações

Os vídeos em `demo/` mostram o sistema em duas situações:

| Arquivo | Cena |
|---|---|
| `armazem_cftv.mp4` | CFTV de galpão, cinco pessoas, uma sem capacete |
| `cabine_empilhadeira.mp4` | Câmera de cabine, operador de colete e sem capacete |
| `epi_detect_demo.mp4` | Os dois em sequência |

![Painel de monitoramento](docs/images/demo-cabine.gif)

> As pessoas nesses vídeos são **sintéticas**, geradas por IA. Nenhuma
> pessoa real foi filmada, o que evita qualquer questão de direito de
> imagem ou proteção de dados nas demonstrações.

---

## Limitações

Vale ser explícito sobre o que este projeto **não** é:

- **Não substitui inspeção de segurança.** É uma ferramenta de apoio, não
  um laudo de conformidade com norma regulamentadora.
- **Colete depende de cor.** Um colete refletivo fora do padrão laranja ou
  amarelo pode não ser reconhecido. As faixas HSV estão em `config.py` e
  podem ser ajustadas.
- **Capacete depende de superfície lisa e clara.** Capacete muito escuro,
  muito sujo ou coberto por capuz reduz a confiabilidade.
- **Pessoa precisa aparecer inteira o suficiente.** Se a cabeça sai do
  quadro ou está totalmente obstruída, não há como avaliar o capacete.
- **Não identifica pessoas.** Não há reconhecimento facial nem qualquer
  vínculo com identidade. O rastreamento só mantém um número temporário
  enquanto a pessoa está no quadro.

Se você precisa de precisão maior num ambiente específico, o caminho é
treinar um modelo dedicado com imagens do próprio local, em vez de ajustar
limites de cor.

---

## Licença

Distribuído sob **AGPL-3.0**. Veja [LICENSE](LICENSE).

Esta escolha não é arbitrária: o projeto usa
[Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics), que é
licenciado sob AGPL-3.0. Trabalhos derivados precisam manter a mesma
licença. Se você pretende usar este código num produto de código fechado,
precisa de uma licença comercial da Ultralytics.

---

## Contribuindo

Correções e melhorias são bem-vindas. Antes de abrir um pull request:

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para mais detalhes.

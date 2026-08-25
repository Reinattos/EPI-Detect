# Contribuindo com o EPI Detect

Obrigado por ajudar a melhorar o projeto. Contribuicoes de codigo, documentacao, testes, UX e visao computacional sao bem-vindas.

## Antes de comecar

1. Leia `README.md` e `PROJECT_CONTEXT.md`.
2. Procure uma issue existente antes de abrir outra.
3. Para mudancas grandes, descreva primeiro a proposta e os impactos.
4. Nunca publique imagens de pessoas, credenciais ou dados de ambientes privados.

## Ambiente local

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

python -m pip install -r requirements.txt
```

Execute com:

```bash
python server.py --source webcam
```

## Areas para contribuicao

- novo front-end e acessibilidade;
- testes automatizados;
- classificacao treinada de uso correto/incorreto;
- exportacao ONNX/OpenVINO;
- suporte a multiplas cameras;
- telemetria local sem dados pessoais;
- documentacao e exemplos reproduziveis.

## Regras de implementacao

- preserve a separacao entre captura, inferencia e encoder;
- nao bloqueie o stream aguardando o modelo;
- lembre que OpenCV usa cores BGR;
- mantenha os contratos de `/video_feed` e `/stats`, ou documente a mudanca;
- centralize parametros ajustaveis em `config.py`;
- evite dependencias pesadas sem justificar impacto e alternativa;
- nao apresente cobertura HSV como percentual de confianca.

## Validacao

Execute pelo menos:

```bash
ruff check .
ruff format --check .
pytest
```

Mudancas no detector devem ser testadas com:

- colete corretamente vestido;
- pessoa sem colete;
- colete somente em um braco ou ombro;
- roupa ou objeto fluorescente;
- movimento, baixa luz e oclusao parcial.

Mudancas de desempenho devem informar FPS do stream, inferencias por segundo, hardware e resolucao.

## Pull request

Inclua:

- problema resolvido;
- resumo da abordagem;
- testes executados;
- impacto em precisao e desempenho;
- capturas sem dados pessoais, quando forem necessarias;
- documentacao atualizada.

## Dataset e privacidade

`dataset_epi/raw/` e ignorado pelo Git. Nao remova essa protecao. Use somente imagens autorizadas e anonimize materiais de demonstracao antes de publica-los.

## Licenca das contribuicoes

O codigo original usa a licenca MIT. Ao contribuir, confirme que codigo, dados e modelos enviados podem ser redistribuidos de forma compativel com essa licenca.

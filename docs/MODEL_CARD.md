# Model card da demonstracao

## Uso pretendido

Demonstrar uma arquitetura de visao computacional em tempo real para sinalizar possivel uso de colete de seguranca em webcam ou video.

## O que o sistema realmente faz

- usa um modelo YOLO Pose pre-treinado para localizar pessoas e keypoints;
- calcula uma regiao aproximada do torso;
- procura cores fluorescentes configuradas em HSV;
- exige evidencia nos dois lados do torso;
- aplica maioria temporal para reduzir oscilacao.

O sistema nao possui, nesta versao, um modelo treinado para compreender semanticamente o formato ou a maneira correta de vestir um colete.

## Classes operacionais

- `com_epi`: evidencia compativel com colete vestido;
- `sem_epi`: ausencia de evidencia suficiente;
- `uso_incorreto`: atualmente incorporado ao contador `without_vest`;
- `falso_positivo`: categoria prevista para coleta e avaliacao do dataset.

## Limitacoes conhecidas

- roupas, objetos ou fundos fluorescentes podem causar falso positivo;
- oclusao, contraluz e baixa resolucao podem causar falso negativo;
- a regra bilateral pode rejeitar pessoas vistas muito de lado;
- a estabilizacao temporal introduz pequeno atraso na mudanca de estado;
- thresholds foram calibrados em poucos exemplos e uma webcam;
- nao existem metricas representativas de campo.

## Metricas

Ainda nao publicadas. Nao declare acuracia, precisao ou recall sem um conjunto de teste separado por pessoa, sessao e ambiente.

O conjunto futuro deve medir pelo menos:

- precisao e recall por classe;
- matriz de confusao;
- falso negativo de `sem_epi`/`uso_incorreto`;
- falso positivo provocado por objetos fluorescentes;
- latencia e FPS por hardware.

## Dados

As imagens locais ficam em `dataset_epi/raw/` e sao ignoradas pelo Git. Use apenas dados autorizados. Separe treino, validacao e teste por pessoa ou sessao para evitar vazamento entre conjuntos.

## Uso inadequado

- punicao ou decisao automatica sobre trabalhadores;
- substituicao de inspecao humana;
- alegacao de conformidade legal;
- vigilancia sem base legal e consentimento;
- implantacao critica sem validacao independente.

## Proxima evolucao

Treinar um classificador leve de torso para `com_epi`, `sem_epi` e `uso_incorreto`, exportar para ONNX/OpenVINO e comparar contra o fallback HSV em um conjunto de teste congelado.

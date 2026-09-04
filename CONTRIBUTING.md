# Contribuindo

## Ambiente

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Antes de abrir um pull request

```bash
ruff check .
pytest -q
```

## Mexendo nos limites de detecção

Os valores em `config.py` foram calibrados medindo vídeo real. Se você
mudar algum, **meça o efeito** em vez de ajustar por tentativa.

O padrão que funcionou durante o desenvolvimento foi instrumentar a
função de análise e imprimir os valores intermediários por quadro:
cobertura antes e depois de cada máscara, desvio padrão do brilho, e o
HSV médio dentro do recorte. Foi assim que se descobriu que um falso
positivo de capacete vinha do recorte cair no piso, e não de um limite
mal escolhido — o HSV médio dentro dele era cinza dessaturado, e a
cobertura bruta era zero antes de qualquer filtro.

Um teste de regressão em dois vídeos com características opostas (plano
aberto e plano fechado) pega a maioria dos problemas. Corrigir um caso
e quebrar o outro aconteceu várias vezes.

## Estilo

- Comentário explica **por quê**, não o que a linha faz.
- Valor numérico calibrado leva junto a medição que o justifica.
- Nome de função e variável em inglês; comentário e docstring em português.

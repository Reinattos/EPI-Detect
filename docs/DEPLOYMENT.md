# Implantacao

## Demo local

```bash
python server.py --source webcam --port 5000
```

Essa e a unica forma suportada atualmente.

O host padrao e `127.0.0.1`. Nao use `--host 0.0.0.0` sem implementar os controles descritos abaixo.

## Nao expor diretamente

O servidor embutido do Flask e adequado para desenvolvimento. Ele nao fornece autenticacao, HTTPS, limites de requisicao, isolamento de camera ou persistencia segura.

Antes de qualquer implantacao em rede:

1. defina autenticacao e autorizacao;
2. use proxy reverso com HTTPS;
3. restrinja origem e acesso ao stream;
4. estabeleca politica de retencao e privacidade;
5. execute como usuario sem privilegios;
6. adicione logs sem dados pessoais;
7. monitore `/health`;
8. valide modelo, hardware e recuperacao da camera;
9. revise licencas dos pesos e dependencias.

## Desempenho

Capture, inferencia e encoder ja sao independentes. Para hardware CPU, priorize `INPUT_SIZE`, `DETECTION_INTERVAL`, resolucao da webcam e `TORCH_THREADS`. Compare PyTorch com ONNX/OpenVINO antes de escolher o runtime de producao.

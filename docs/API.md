# API HTTP

Contrato do backend Flask usado pelo dashboard. A API ainda nao possui versionamento; mudancas incompatíveis devem atualizar este documento e o front-end no mesmo pull request.

## Estados do pipeline

| Estado | Significado |
|---|---|
| `starting` | processo inicializando |
| `waiting_camera` | fonte ainda nao entregou um frame |
| `loading_model` | camera ativa e modelo carregando |
| `running` | camera e modelo operacionais |
| `error` | falha que requer atencao ou nova tentativa |

## `GET /`

Retorna o dashboard HTML. Resposta esperada: `200 text/html`.

## `GET /video_feed`

Retorna stream MJPEG com `Content-Type: multipart/x-mixed-replace; boundary=frame`. A conexao permanece aberta. O primeiro frame pode aguardar a inicializacao da camera.

## `GET /stats`

Resposta `200 application/json`:

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

- `with_vest`: pessoas classificadas com EPI;
- `without_vest`: pessoas sem EPI ou com uso incorreto;
- `total`: quantidade de pessoas na ultima inferencia;
- `fps`: quadros JPEG codificados no ultimo segundo;
- `det_fps`: inferencias finalizadas no ultimo segundo;
- `alert`: verdadeiro quando `without_vest > 0`;
- `status`: estado atual do pipeline;
- `error`: mensagem operacional ou `null`.

Os contadores refletem a ultima inferencia concluida, nao cada frame visual.

## `GET /health`

Resposta saudavel ou em inicializacao (`200`):

```json
{
  "ok": true,
  "status": "loading_model",
  "camera_ready": true,
  "model_ready": false
}
```

Retorna `503` quando `status=error`. Esse endpoint indica saude operacional, nao precisao do modelo.

## Seguranca

Nao ha autenticacao, autorizacao, CORS configurado ou HTTPS. O servidor deve permanecer local durante a demo. Nao o exponha diretamente na internet.

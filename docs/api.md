# API do servidor web

O `server.py` expõe uma interface HTTP para consumir o vídeo anotado e as
estatísticas de fora do processo.

## Stream de vídeo

```
GET /video_feed
```

MJPEG contínuo, pronto para usar direto numa tag `<img>`:

```html
<img src="http://localhost:5000/video_feed">
```

## Estatísticas

```
GET /stats
```

```json
{
  "ok": 4,
  "no_vest": 0,
  "no_helmet": 1,
  "total": 5,
  "compliance": 80,
  "fps": 3.2,
  "people": [
    {
      "track_id": 3,
      "has_vest": true,
      "has_helmet": false,
      "vest_score": 0.62,
      "helmet_score": 0.00,
      "violation_seconds": 4.2
    }
  ]
}
```

Os campos `vest_score` e `helmet_score` trazem a cobertura medida, útil
para calibrar os limites num ambiente novo: rode com pessoas de EPI e sem,
observe a separação entre os dois grupos e escolha o corte no meio.

## Saúde

```
GET /health
```

```json
{ "status": "ok", "model": "yolov8n-pose.pt", "imgsz": 1280 }
```

## Zonas de risco

```
GET  /api/zones
POST /api/zones
```

Corpo do POST:

```json
{
  "action": "add",
  "zone": {
    "name": "Área de carga",
    "require": ["vest", "helmet"],
    "points": [[0.1, 0.2], [0.6, 0.2], [0.6, 0.9], [0.1, 0.9]]
  }
}
```

Coordenadas são normalizadas entre 0.0 e 1.0, então a zona continua
válida se a resolução da câmera mudar. Ações aceitas: `add`, `update`,
`delete` e `replace_all`.

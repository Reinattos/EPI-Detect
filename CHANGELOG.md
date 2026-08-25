# Changelog

## [1.0.0] — 2026-08-21

### Adicionado
- Detecção de pessoas com YOLOv8n em tempo real
- Análise HSV para coletes laranja e amarelo high-vis
- Overlay profissional com Pillow (bounding boxes, labels, barra de status)
- Suporte a webcam e vídeo demo via argparse
- Captura threaded (sem blocking I/O)
- Indicador de cobertura de colete por pessoa
- Exportação de vídeo processado com `--save`

## [1.1.0] — 2026-08-21

### Alterado
- Pipeline assincrono para separar captura, inferencia e stream
- Evidencia bilateral para rejeitar colete em apenas um braco
- Estabilizacao temporal por pessoa
- Ajustes de desempenho para CPU e stream de 20 FPS
- Cor de ausencia/uso incorreto corrigida para vermelho em BGR
- Documentacao e higienizacao de dados para publicacao
- Estados explicitos de carregamento e erro no dashboard
- Endpoint de saude e contrato formal da API
- Testes automatizados, Ruff e CI com GitHub Actions
- Licenca MIT e documentacao de limitacoes do modelo

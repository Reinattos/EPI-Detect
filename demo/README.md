# Vídeos de demonstração

| Arquivo | Cena | Resultado |
|---|---|---|
| `epi_detect_demo.mp4` | Os dois clipes em sequência | Demonstração completa, 18s |
| `cabine_empilhadeira.mp4` | Câmera de cabine de empilhadeira | Colete detectado, capacete ausente — conformidade 0% |
| `armazem_cftv.mp4` | CFTV de galpão logístico, cinco pessoas | Quatro conformes, uma sem capacete — conformidade 80% |

As pessoas nesses vídeos são **sintéticas**, geradas por IA. Nenhuma pessoa
real foi filmada, o que evita qualquer questão de direito de imagem ou
proteção de dados no material de demonstração.

Para reproduzir o processamento em um vídeo próprio:

```bash
python render.py seu_video.mp4
```

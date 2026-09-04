# Política de segurança

## Reportando uma vulnerabilidade

Abra uma issue descrevendo o problema. Para algo sensível, use o canal
privado de security advisory do GitHub em vez de uma issue pública.

## Considerações de privacidade

Este projeto processa imagem de pessoas. Alguns pontos importam:

- **Nada é gravado por padrão.** `detect.py` e `server.py` processam em
  memória e não persistem quadros nem resultados.
- **Não há identificação de pessoas.** Não existe reconhecimento facial.
  O identificador de rastreamento é um número temporário, válido apenas
  enquanto a pessoa está no quadro, e não é vinculado a nenhum cadastro.
- **Credenciais de câmera.** URLs RTSP costumam conter usuário e senha.
  Mantenha-as em `settings_local.json` ou em variável de ambiente, nunca
  no código. `settings_local.json` está no `.gitignore`.
- **Monitoramento de trabalhadores** é regulado em várias jurisdições. No
  Brasil, aplica-se a LGPD. Antes de usar em produção, verifique base
  legal, transparência com as pessoas monitoradas e política de retenção.

# StremioProxyWAN v0.2.2 — WebPlayer WAN estável

## Correcção de estabilidade

- Descoberta automática do servidor de streaming no WebPlayer público: a resposta `localStorage.json` passa a anunciar `https://WAN_HOST/`, mantendo a origem interna apenas no WebPlayer LAN.
- Mantidos Basic Auth, sessões assinadas, cookies, IP/hostname TLS verificado no backend, HTTPS público, renovação TLS-ALPN-01 e isolamento do addon de conta.
- As regras Nginx são geradas a partir de configuração; não existe IP ou password embutido na release.
- Testes no Nginx isolado: 401 sem autenticação, 200 com conta de teste e endereço WAN exacto, 200 no endpoint de settings. Os testes unitários aprovados incluem validação do URL WAN, porta não padrão e preservação das rotas autorizadas.
- Exercícios funcionais anteriores: WebPlayer via WAN, áudio, vídeo, legendas, transcoding, retoma e recuperação após reboot no ambiente de QA.
- Artefactos: pacote Debian, código-fonte e SHA256SUMS.

## Limites

O addon privado e a integração com a aplicação Stremio Windows/TV são experimentais: a autenticação de browser não equivale à autenticação do Core pela aplicação nativa. A release estável refere-se ao fluxo WebPlayer WAN com Basic Auth/sessões e proxy de media. Não exponha o backend Stremio nem a administração LAN directamente na Internet.

## Upgrade em servidor existente

Conservar `/etc/stremioproxywan` (certificados, utilizadores e chaves), `/var/lib/stremioproxywan-addon` e configuração Nginx como backup. Instalar o `.deb` da release e executar `stremioproxywan check` seguido de `stremioproxywan apply`. O package não reinicializa as credenciais. Reverter apenas com uma cópia de backup consistente, não com alterações manuais à configuração gerada.
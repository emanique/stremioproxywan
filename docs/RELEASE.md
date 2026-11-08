# Release candidate v0.1.0 — distribuição genérica

Primeira distribuição parametrizável para Debian e Ubuntu.

## Componentes

- Proxy HTTPS com domínio/IP WAN, backend LAN e portas configuráveis.
- Certificado WAN confiável ou autoassinado com SAN DNS/IP, sem desligar a validação TLS do backend.
- Autenticação Basic bcrypt e sessão HMAC via cookie para HLS.
- CLI para adicionar/remover utilizadores e alterar password WAN.
- Porta HTTP WAN desactivada por defeito; redireccionamento ou proxy legado explicitamente configuráveis.
- Backups, nginx -t e rollback antes do reload.
- Pacote Debian architecture all e arquivo tar.gz de origem, com SHA-256.

## Limitações

- Não gere DNS, NAT, firewall, Let's Encrypt, CA privada ou actualizações do Stremio.
- Certificados autoassinados exigem confiança do cliente.
- Mudar password não invalida cookies assinados existentes (TTL 12 horas).
- A Stremio App LAN deve utilizar o endpoint interno do Core.
- O modo HTTP legacy_proxy não tem autenticação WAN.
- Migrar um virtual host antigo requer procedimento separado.

## Qualificação

A parametrização, o teste nginx -t em configuração de ensaio, a construção .deb/tar.gz e checksums foram executados localmente. Instalação/rollback num host limpo e testes funcionais com WAN real, diversos certificados e vários browsers continuam pendentes. Uma tag estável deve identificar uma revisão integral e verificável do repositório; não criar uma tag de produção se a paridade com os artefactos não tiver sido confirmada.

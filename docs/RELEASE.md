# Release candidate v0.1.2 — distribuição genérica

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

## Adições v0.1.2

- Descoberta do IP LAN e do hostname HTTPS correspondente ao certificado apresentado pelo Stremio.
- Geração do nome a partir de octetos do IP separados por hífen e do wildcard SAN do certificado.
- Validação da identidade e da cadeia TLS com CA configurada, sem desligar a verificação.
- Reavaliação no comando discover, check e apply; sem reconciliação periódica em background.
- Testes de mudança de IP, domínio do certificado e rejeição de certificado inválido.

## Fecho v0.1.2 (IP LAN fixo)

- IP do Stremio definido uma única vez durante a instalação; não há monitorização periódica nem alteração automática desse IP.
- Descoberta do nome TLS a partir do certificado apresentado pelo Stremio, com verificação da CA.
- Testes adicionais de ausência de escrita/reload no Nginx quando a identidade TLS não passa na validação.
- 20 testes unitários de configuração, segurança e descoberta aprovados; Nginx de ensaio passou no nginx -t.
- Sem alterações automáticas ao servidor de produção; instalação e rollback em máquina limpa continuam pendentes de certificação antes de classificar esta versão como estável.

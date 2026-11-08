# Operações

## Requisitos

Debian/Ubuntu, Nginx com auth_request, Python 3, openssl, apache2-utils (htpasswd) e systemd. Confirmar DNS/NAT/portas WAN manualmente. O proxy deve alcançar o Stremio na LAN.

## Configuração inicial

1. Instalar o pacote .deb.
2. Executar stremioproxywan configure --set CHAVE=VALOR com todos os endereços da instalação.
3. Escolher wan_tls_mode=trusted com ficheiros wan_cert e wan_key, ou wan_tls_mode=selfsigned.
4. Executar stremioproxywan user add ADMIN, preenchendo a password duas vezes.
5. Executar stremioproxywan check e stremioproxywan apply.
6. Testar systemctl is-active nginx stremioproxywan-session.service.
7. Testar acesso WAN sem sessão (401), login em /_session/start, playlist e segmentos HLS, e byte ranges.
8. Testar Stremio App LAN directamente no endpoint interno do Core.

## Actualização

Configuração e secrets residem em /etc/stremioproxywan e não devem ser incluídos no pacote nem no Git. Não recriar uma password ou HMAC em upgrades automáticos. Configure e aplique alterações após backup.

## Password e utilizadores

sudo stremioproxywan user password ADMIN

sudo stremioproxywan user add OUTRO

sudo stremioproxywan user list

sudo stremioproxywan user remove OUTRO

Hashes são bcrypt. Sessões existentes continuam válidas por até 12 horas após mudança de password.

## Rollback

O instalador guarda snapshots backup-stremioproxywan-*.conf em /etc/stremioproxywan. Para voltar a uma configuração anterior, copie o snapshot escolhido para /etc/nginx/sites-available/stremioproxywan.conf, execute nginx -t e só então systemctl reload nginx. A falha de nginx -t durante apply provoca reposição automática da configuração anterior.

## Avisos de segurança

A porta HTTP legacy_proxy não usa autenticação HTTPS. Não exponha sem aceitar explicitamente esse risco. Uma WAN autoassinada exige que cada cliente confie no certificado ou na CA. Não desligue proxy_ssl_verify para HTTPS interno. Nunca exponha 127.0.0.1:18765 e não publique /etc/stremioproxywan, chaves TLS ou bases de password.

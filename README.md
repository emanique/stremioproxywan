# StremioProxyWAN

**Distribuição genérica v0.1.0** para Debian/Ubuntu. Nginx reverse proxy para Stremio WebPlayer, com autenticação WAN, sessão assinada para HLS e domínios/IP WAN e LAN totalmente configuráveis.

## Arquitectura

~~~text
Browser WAN -> HTTPS Nginx Proxy -> Stremio WebPlayer/Core na LAN
Stremio App interna -> endpoint HTTPS do Core na LAN (directo)
~~~

O pacote não altera a VPN, o Pi-hole, o Stremio, o DNS público, o NAT nem a firewall.

## Instalação

~~~bash
sudo apt install ./stremioproxywan_0.1.0_all.deb
sudo stremioproxywan configure \
 --set wan_host=stream.exemplo.com \
 --set wan_address_mode=ddns \
 --set wan_port=443 \
 --set lan_host=192.168.10.20 \
 --set lan_http_port=8080 \
 --set lan_core_port=11470 \
 --set backend_scheme=https \
 --set backend_host=stremio-interno.exemplo.net \
 --set backend_port=12470 \
 --set backend_tls_name=stremio-interno.exemplo.net \
 --set wan_tls_mode=selfsigned \
 --set http_policy=disabled
sudo stremioproxywan user add admin
sudo stremioproxywan check
sudo stremioproxywan apply
~~~

Os valores de exemplo não são destinos operacionais. É obrigatório configurar os endereços reais antes de aplicar. A instalação do pacote **não altera o Nginx automaticamente**.

## WAN com IP dinâmico (DDNS)

O modo `wan_address_mode=ddns` permite publicar o serviço através de um hostname estável, por exemplo `stream.meudominio.net`, mesmo quando o ISP altera o IP público. Configure `wan_host` com esse hostname e mantenha um actualizador DDNS no router, no serviço DNS ou num agente externo. **O Nginx não precisa de conhecer o IP WAN actual nem precisa de ser reiniciado quando esse IP muda.**

Exemplo:

~~~bash
sudo stremioproxywan configure --set wan_address_mode=ddns --set wan_host=stream.meudominio.net
sudo stremioproxywan check
sudo stremioproxywan apply
~~~

Modos de endereço WAN:

- `ddns`: hostname com IP WAN variável, actualizado externamente.
- `static`: hostname com DNS público estático.
- `direct_ip`: acesso por IPv4 WAN, usando `wan_host` igual ao IPv4. Se esse IP mudar, será necessário descobrir e comunicar o novo IP; não existe nome estável.

**Atenção:** a actualização DDNS não atravessa CGNAT, não cria regras NAT/firewall e não substitui um certificado válido. Em `selfsigned`, o certificado inclui SAN para o hostname ou IP configurado; em `trusted`, o certificado precisa de cobrir o mesmo hostname/IP. O pacote não guarda credenciais DDNS nem modifica a WAN do router.

## WAN com ou sem certificado público

- **selfsigned:** cria certificado autoassinado com SAN DNS/IP WAN quando ainda não existe. Os browsers terão de confiar no certificado.
- **trusted:** utilize um certificado de CA pública ou privada e forneça os caminhos usando wan_cert e wan_key. A renovação de certificados não é automática.
- **backend HTTPS:** verifica o certificado e o SNI. Para CA privada interna, indique backend_ca. **Não desactive** proxy_ssl_verify para suportar WAN autoassinada.
- **backend HTTP:** é possível em rede interna protegida, mas não cifra o tráfego proxy→Core.

## Alterar login/password WAN

~~~bash
sudo stremioproxywan user add admin
sudo stremioproxywan user password admin
sudo stremioproxywan user list
sudo stremioproxywan user add outro
sudo stremioproxywan user remove outro
~~~

A password é introduzida duas vezes e guardada com bcrypt (htpasswd). Não é colocada em argumentos da linha de comandos. **Sessões já emitidas continuam válidas até 12 horas**, mesmo após mudar a password.

Abra o endereço HTTPS WAN terminado em /_session/start para iniciar a sessão autenticada.

## Política HTTP WAN

- **disabled:** não publica a porta 80 (por defeito).
- **redirect:** redirecciona HTTP para HTTPS.
- **legacy_proxy:** encaminha HTTP para a porta LAN 8080 **sem autenticação**. É uma opção de retrocompatibilidade com risco explícito.

## Operação

O comando apply cria backup da configuração anterior, testa nginx -t e faz reload, sem reiniciar o Stremio. A chave HMAC e utilizadores ficam no host, fora do repositório. O acesso de sessão só escuta em 127.0.0.1:18765. A reescrita HLS mediaURL é limitada ao domínio WAN configurado e não altera outros fluxos.

Arquivos sensíveis que nunca devem ser publicados: users.htpasswd, session.key, chaves TLS privadas e config.json da instalação.

## Construção dos artefactos

~~~bash
python3 -m unittest discover -s tests -v
bash packaging/build.sh dist
(cd dist && sha256sum -c SHA256SUMS)
~~~

A distribuição produz o pacote .deb (architecture all), um tar.gz de código-fonte e SHA256SUMS. O pacote não inclui passwords, chaves de sessão, certificados ou dados de utilizador.

Ver [Operação e rollback](docs/OPERATIONS.md) e [Notas da versão](docs/RELEASE.md).

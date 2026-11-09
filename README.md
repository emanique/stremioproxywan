# StremioProxyWAN

**Distribuição genérica v0.2.1** para Debian/Ubuntu. Nginx reverse proxy para Stremio WebPlayer, com autenticação WAN, sessão assinada para HLS e domínios/IP WAN e LAN totalmente configuráveis.

**Release:** [v0.2.1 — packages e hashes](https://github.com/emanique/stremioproxywan/releases/tag/v0.2.1). A distribuição mantém o instalador `.deb` e o arquivo de origem `.tar.gz`, com `SHA256SUMS`. Os parágrafos sobre v0.1.x abaixo documentam a evolução histórica e não indicam a versão actual de instalação. A versão v0.2.1 contém os desenvolvimentos posteriores de addon privado, media endpoints autenticados e metadados para reprodução, mas não garante autenticação nativa universal da aplicação Stremio Windows.

## Arquitectura

~~~text
Browser WAN -> HTTPS Nginx Proxy -> Stremio WebPlayer/Core na LAN
Stremio App interna -> endpoint HTTPS do Core na LAN (directo)
~~~

O pacote não altera a VPN, o Pi-hole, o Stremio, o DNS público, o NAT nem a firewall.

## Instalação

~~~bash
sudo apt install ./stremioproxywan_0.2.1_all.deb
sudo stremioproxywan configure \
 --set wan_host=stream.exemplo.com \
 --set wan_address_mode=ddns \
 --set wan_port=443 \
 --set lan_host=192.168.10.20 \
 --set lan_http_port=8080 \
 --set lan_core_port=11470 \
 --set backend_scheme=https \
 --set backend_port=12470 \
 --set backend_identity_mode=stremio_auto \
 --set wan_tls_mode=selfsigned \
 --set http_policy=disabled
sudo stremioproxywan user add admin
sudo stremioproxywan check
sudo stremioproxywan apply
~~~

Os valores de exemplo não são destinos operacionais. É obrigatório configurar os endereços reais antes de aplicar. A instalação do pacote **não altera o Nginx automaticamente**.

## Descoberta automática do certificado Stremio LAN

O endereço HTTPS interno do Stremio tem duas partes: **IP LAN com pontos substituídos por hífen** + **sufixo DNS do certificado**. Exemplo validado em 2026-11-08:

- IP LAN: `192.168.1.199`.
- Certificado SAN: `*.519b6502d940.stremio.rocks`.
- Endereço HTTPS resultante: `192-168-1-199.519b6502d940.stremio.rocks:12470`.

Em `backend_identity_mode=stremio_auto` (predefinição), o comando `discover` resolve `lan_host`, lê o SAN do certificado apresentado pelo serviço LAN na porta `backend_port`, constrói o hostname e valida a ligação com a CA configurada. `check` e `apply` repetem a descoberta; `apply` só carrega a configuração após a validação.

~~~bash
sudo stremioproxywan configure \
  --set lan_host=192.168.1.199 \
  --set backend_port=12470 \
  --set backend_identity_mode=stremio_auto
sudo stremioproxywan discover
sudo stremioproxywan check
sudo stremioproxywan apply
~~~

**IP LAN fixo por instalação:** o utilizador define `lan_host` uma única vez. Esse endereço permanece igual durante o funcionamento normal e não existe serviço periódico para detectar mudanças de IP. A descoberta automática serve para identificar e verificar o hostname HTTPS do certificado Stremio durante `discover`, `check` e `apply`. Se a administração alterar deliberadamente o IP ou o certificado, deve actualizar a configuração e executar novamente `check` e `apply`. O endereço encontrado é verificado contra a CA configurada; detectar um SAN não significa confiar num certificado desconhecido.

Para certificados internos sem uma CA confiável, disponibilize primeiro uma CA de confiança em `backend_ca` ou utilize o modo manual e uma arquitectura TLS apropriada. Não desligue a verificação TLS para contornar certificados inválidos.

## Pré-requisito: certificado HTTPS interno Stremio

Numa instalação nova, o Core pode arrancar temporariamente com um certificado autoassinado, enquanto tenta obter o wildcard público stremio.rocks. O modo stremio_auto do ProxyWAN **não ignora erros TLS**; requer certificado verificável e SAN DNS utilizável. Aguarde a emissão do certificado confiável e execute discover/check. Se utilizar uma CA privada, instale a CA no Proxy e configure backend_ca.

Em redes internas isoladas onde o Core não obtém um certificado validável, existe uma alternativa **explícita**, sem downgrade silencioso: configurar backend_identity_mode=manual, backend_scheme=http, backend_host=IP_LAN_STREMIO e backend_port=8080. O browser WAN continua em HTTPS, mas o tráfego Proxy→Stremio fica em HTTP na LAN; use apenas em rede confiável. Este caminho necessita de validação funcional própria.

O certificado wildcard partilhado do Stremio pode ter chave privada comum a diferentes instalações. Um certificado com cadeia pública válida não implica uma identidade criptográfica exclusiva do servidor. Para cenários com fronteiras de segurança estritas, preferir certificado privado controlado pelo operador, emitido por CA confiável.

## HTTPS público com porta 80 fechada

O release 0.1.3 inclui o mecanismo de renovação Let’s Encrypt **TLS-ALPN-01** através de TCP/443. Não requer TCP/80. O nome WAN tem de resolver para o endereço público cujo NAT encaminha TCP/443 para o ProxyWAN, e esse encaminhamento não pode interferir com o desafio ACME.

Para efectuar a emissão inicial, instale `lego`, faça backup de `/etc/stremioproxywan`, pare temporariamente o Nginx, execute `lego --path /etc/stremioproxywan/lego --accept-tos --email CONTACTO_REAL --domains NOME_WAN --tls run` e arranque novamente o Nginx, mesmo se houver erro. O contacto deverá ser autorizado pelo operador. Instale o certificado e a cadeia pública (ficheiro .crt e .issuer.crt) e a chave privada de modo 0600 na localização WAN configurada. Alterar `wan_tls_mode=trusted`, executar `check` e `apply` e confirmar `curl` HTTPS sem `-k`.

Para a renovação: guardar o contacto aprovado em `/etc/stremioproxywan/acme-email` com modo 0600 e activar `stremioproxywan-cert-renew.timer`. O timer apenas interrompe Nginx quando o certificado tiver menos de 30 dias de validade. Durante a emissão TLS-ALPN-01 existe uma breve interrupção HTTPS; o serviço volta a arrancar mesmo após falha. Backup seguro de contas ACME/chaves é obrigatório.

A configuração `http_policy=disabled` exige remover o site default do Nginx que possa escutar na porta 80. Confirmar com `ss -lntp`. O caminho legado `/login` redirecciona para `/_session/start`; a autenticação WAN é via utilizadores `htpasswd` e sessão assinada.

**Diagnóstico:** um 401 com `WWW-Authenticate: Basic` confirma exigência de login, não erro no backend. Mensagens `password mismatch` indicam credencial incorrecta; use `sudo stremioproxywan user password admin` para a alterar, sem a colocar na linha de comandos. O pacote 0.1.3 preserva `config.json`, `users.htpasswd` e `session.key` existentes.

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

## Link fixo partilhado — WebPlayer externo (v0.1.3 QA)

Na primeira aplicação da configuração, o ProxyWAN gera um segredo aleatório de 256 bits em `/etc/stremioproxywan/shared-link.token`, persistente após reboot e actualização, legível somente por root e pelo grupo www-data. O token não é publicado no GitHub, não é introduzido no ficheiro `config.json` e não aparece no access log do endpoint de activação.

Obter o único link de acesso (comando executado **localmente como root**):

~~~bash
sudo stremioproxywan link show
~~~

O endereço é semelhante a `https://str.lusosolutions.com/activate/<segredo-aleatorio>`. Qualquer pessoa que possua o link pode obter uma sessão para o WebPlayer, sem credenciais Basic, durante a validade do link. Cada cliente recebe um cookie assinado e independente de 12 horas, sendo depois redireccionado para `/`. Não altera os utilizadores/password já existentes. A porta 80 continua fechada se `http_policy=disabled` e o site default do Nginx estiver desactivado.

**Risco:** o link é uma credencial partilhada de tipo bearer, não uma conta individual. Evitar enviá-lo por canais públicos, fotografias e sistemas com pré-visualização automática. Não suporta nesta versão revogação por cliente nem autenticação directa da aplicação Stremio oficial. Se o endereço for comprometido, a rotação do segredo exige um procedimento administrativo; os cookies já emitidos continuam válidos até expirarem, salvo alteração da chave HMAC de sessão (que invalida todas as sessões).

A rota exacta de activação devolve HTTP 302 e estabelece um cookie com Secure, HttpOnly e SameSite=Lax. Um token incorrecto devolve HTTP 404. Não guardar o URL com o token em históricos, logs de reverse proxy anteriores ou ferramentas de monitorização.

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

## Experimental account-bound addon (0.1.4)

This addon is **not** a replacement for the native Stremio streaming-server
authentication. The SDK cannot make the Windows client attach a Stremio
`authKey` to `/settings`, `/device-info` or playback requests. It only
provides a private Stremio addon manifest bound to a verified account.

To use, first authenticate to the browser WebPlayer via the existing shared
activation link, then open `https://<WAN-HOST>/_addon/configure` using the
same browser/origin and the same signed-in Stremio account. Press **Associar
conta actual**. If not approved, the page shows the Stremio account id.
An operator explicitly permits that ID on the VM3 with:

```bash
sudo env PYTHONPATH=/usr/lib/stremioproxywan python3 -m addon_auth.admin allow 'STREMIO_ACCOUNT_ID'
# revoke all existing manifests for the account:
sudo env PYTHONPATH=/usr/lib/stremioproxywan python3 -m addon_auth.admin revoke 'STREMIO_ACCOUNT_ID'
sudo env PYTHONPATH=/usr/lib/stremioproxywan python3 -m addon_auth.admin list
```

Revisit configure after approval to receive a private manifest URL; install
it in the Stremio client. Anyone who possesses that URL may access the addon
until its account is revoked, so do not share it. The service stores only
hashed capability values and account IDs, never Stremio authKeys/passwords.
Only the proxy's existing authenticated browser session can initiate pairing.
The addon currently provides an empty catalog and intentionally **does not
proxy streaming content**. The general Stremio Core remains protected by
ProxyWAN's prior Basic/session mechanism. The addon service listens on
127.0.0.1:18766, with account policy persisted at
`/var/lib/stremioproxywan-addon/accounts.json`.

Account pairing requires a browser with a Stremio WebPlayer session saved
under this exact HTTPS origin. The `authKey` is verified by `api.strem.io`
and is not recorded by this server. Approve an account only after confirming
the identifier through an independent channel.

### Stremio addon CORS and installation (v0.1.5)

Addon manifests and catalog endpoints on `/_addon/<capability>/...` return
`Access-Control-Allow-Origin: *`, which the Stremio addon HTTP transport
requires. This is restricted to capability-protected addon resources, not
the ProxyWAN Core, the `/_addon/pair` route, or the authenticated
`/_addon/configure` page. An install `stremio://` deep link may not be
handled consistently by every desktop client; the configure page also
provides the HTTPS manifest URL for manual installation in Addons.

### Windows installation correction (v0.1.6)

The association screen now offers only the HTTPS manifest URL and explicit
manual Addons installation instructions. It no longer opens the native
\`stremio://\` deep link, which some Windows client builds route to a
\`Page not found\` screen. A valid addon manifest is separate from the
custom streaming-server address; the addon cannot authenticate that Core
connection and never claims to do so.

### Account addon functional diagnostic catalog (0.1.7)

The private account addon now advertises `catalog`, `meta`, and `stream`
resources. A single movie-type diagnostic item, **StremioProxyWAN - Conta
autorizada**, is shown in its own catalog for a client holding an
approved, revocable manifest capability. Its metadata explicitly states
that this proves only addon access. Its stream response is intentionally
empty: an addon capability is not automatically a Core authorization,
and no broad Core endpoint or video URL is exposed by this version.

The account's existing manifest URL remains valid across this upgrade.
Clients that cache the old manifest may need an addon refresh to see the
new catalog resource; no token rotation is required.

### Stremio Windows meta resolution (0.1.8)

The manifest declares idPrefixes = ["proxywan:"] globally and explicitly for both meta and stream resources. Clients can select this addon for the diagnostic catalog item proxywan:connection. No Core authentication or video stream access is changed. Existing private manifest URLs remain valid. Refresh addon metadata if the client has cached manifest 0.2.0.

### Core authenticated handshake pilot (v0.1.9)

An installed private addon capability can authenticate an **isolated**
Core handshake URL prefix: https://WAN/_core/CAPABILITY/settings,
/network-info, /device-info and /casting. Nginx issues an internal
auth_request to the loopback addon service. Only GET is forwarded; all
other Core endpoints remain covered by their previous session/Basic
authentication. All capability-bearing request paths are excluded from
Nginx access logging. This tests whether the native client keeps a URL
prefix when configured as a streaming server: it does not prove that it
will do so. The existing manifest remains valid and is not rotated.
Never send the capability-bearing URL in support logs or screenshots.

The authenticated browser configuration page can now generate a separate
experimental Core URL via POST /_addon/core-link. This generates another
revocable capability for the validated account; it does NOT change the
installed addon manifest. Only the four read-only handshake endpoints
are authorized. Do not use it for playback or expect arbitrary Core
requests to succeed. This is strictly an interoperability probe.

### Private completed-media playback (0.2.0)

The addon now lists completed torrents already loaded by the internal Core
(active.json, fixed LAN address), and exposes their metadata and a private
HTTPS media URL. No magnet creation, tracker input, arbitrary file indices,
or external destination URLs are accepted. Nginx validates the addon
capability and completed torrent hash on every /_media/ request via an
internal loopback auth_request. Byte-range responses are proxied from the
existing Stremio Core with TLS validation. The original browser session
path and the principal Streaming Server URL remain authenticated. This is
a narrow pilot: TV/HLS and remote native playback are not yet validated.

### Native player MKV stream metadata (0.2.1)

For the private MKV/HEVC media URL, stream.behaviorHints.notWebReady
is explicitly true as required by the Stremio addon protocol for non-MP4
HTTP(S) streams. behaviorHints.filename is populated with the original
filename to support recognition and subtitle addons. The endpoint,
capability, media bytes, and streaming server authentication remain
unchanged. This does not guarantee external-player integration.

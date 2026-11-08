#!/usr/bin/env bash
# Renew trusted WAN TLS through TLS-ALPN-01; never open HTTP/80.
set -Eeuo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
ROOT=/etc/stremioproxywan
CONFIG="$ROOT/config.json"
EMAIL="$ROOT/acme-email"
LEGO_ROOT="$ROOT/lego"
DOMAIN="$(python3 - "$CONFIG" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
if d.get("wan_tls_mode")!="trusted" or d.get("http_policy")!="disabled":
    raise SystemExit("ACME renewal needs trusted HTTPS-only mode")
print(d["wan_host"])
PY
)"
[[ "$DOMAIN" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]{1,250}$ ]] || exit 2
[[ -f "$EMAIL" && ! -L "$EMAIL" ]] || { echo "Root-only ACME contact missing"; exit 2; }
[[ "$(stat -c %a "$EMAIL")" == "600" ]] || { echo "Unsafe ACME contact permissions"; exit 2; }
CERT="$ROOT/tls/fullchain.pem"
KEY="$ROOT/tls/privkey.pem"
[[ -f "$CERT" && -f "$KEY" ]] || exit 2
if openssl x509 -checkend 2592000 -noout -in "$CERT" >/dev/null; then
    echo "Certificate valid for more than 30 days; no downtime"
    exit 0
fi
[[ "$(id -u)" == "0" ]] || exit 2
TMP="$(mktemp -d "$ROOT/tls/.renew-XXXXXXXX")"
chmod 700 "$TMP"
restore_service() { systemctl start nginx; rm -rf "$TMP"; }
trap restore_service EXIT
systemctl stop nginx
lego --path "$LEGO_ROOT" --email "$(cat "$EMAIL")" --domains "$DOMAIN" --tls --tls.port ':443' renew --days 30
SRC="$LEGO_ROOT/certificates/$DOMAIN"
[[ -s "$SRC.crt" && -s "$SRC.issuer.crt" && -s "$SRC.key" ]] || exit 3
cat "$SRC.crt" "$SRC.issuer.crt" > "$TMP/fullchain.pem"
install -m 600 "$SRC.key" "$TMP/privkey.pem"
openssl x509 -in "$TMP/fullchain.pem" -noout -checkend 2592000 || exit 3
openssl x509 -in "$TMP/fullchain.pem" -pubkey -noout > "$TMP/cert.pub"
openssl pkey -in "$TMP/privkey.pem" -pubout > "$TMP/key.pub"
cmp -s "$TMP/cert.pub" "$TMP/key.pub" || exit 3
cp -a "$CERT" "$TMP/old.crt"
cp -a "$KEY" "$TMP/old.key"
install -m 644 "$TMP/fullchain.pem" "$CERT"
install -m 600 "$TMP/privkey.pem" "$KEY"
if ! nginx -t; then
    install -m 644 "$TMP/old.crt" "$CERT"
    install -m 600 "$TMP/old.key" "$KEY"
    exit 4
fi
echo "Renewed trusted HTTPS certificate for $DOMAIN"

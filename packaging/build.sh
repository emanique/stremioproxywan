#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
VERSION="$(cat VERSION)"
OUT="dist"
if [ "$#" -gt 0 ]; then OUT="$1"; fi
mkdir -p "$OUT"
OUT="$(realpath "$OUT")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/stremioproxywan_${VERSION}_all"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/stremioproxywan/stremioproxywan" "$ROOT/usr/lib/stremioproxywan/addon_auth" "$ROOT/usr/bin" "$ROOT/usr/libexec" "$ROOT/lib/systemd/system" "$ROOT/usr/share/doc/stremioproxywan"
cp stremioproxywan/*.py "$ROOT/usr/lib/stremioproxywan/stremioproxywan/"
cp addon_auth/*.py "$ROOT/usr/lib/stremioproxywan/addon_auth/"
cp README.md "$ROOT/usr/share/doc/stremioproxywan/README.md"
install -m 0644 deploy/systemd/stremioproxywan-addon.service "$ROOT/lib/systemd/system/"
install -m 0755 scripts/renew-tls-alpn.sh "$ROOT/usr/libexec/stremioproxywan-renew-tls"
install -m 0644 deploy/systemd/stremioproxywan-cert-renew.service "$ROOT/lib/systemd/system/"
install -m 0644 deploy/systemd/stremioproxywan-cert-renew.timer "$ROOT/lib/systemd/system/"
cat > "$ROOT/DEBIAN/control" <<EOF
Package: stremioproxywan
Version: $VERSION
Section: web
Priority: optional
Architecture: all
Depends: python3, nginx, openssl, apache2-utils, systemd, lego
Maintainer: StremioProxyWAN maintainers
Description: Configurable authenticated Stremio reverse proxy
 Configures a TLS Nginx WAN proxy and signed browser sessions without shipping secrets.
EOF
cat > "$ROOT/usr/bin/stremioproxywan" <<'EOF'
#!/bin/sh
export PYTHONPATH=/usr/lib/stremioproxywan
exec /usr/bin/python3 -m stremioproxywan.cli "$@"
EOF
chmod 755 "$ROOT/usr/bin/stremioproxywan"
dpkg-deb --build --root-owner-group "$ROOT" "$OUT/stremioproxywan_${VERSION}_all.deb" >/dev/null
ARCHIVE="$OUT/stremioproxywan-$VERSION.tar.gz"
tar --sort=name --mtime='UTC 2026-11-08' --owner=0 --group=0 --numeric-owner \
 -czf "$ARCHIVE" README.md VERSION stremioproxywan addon_auth packaging docs tests scripts deploy
(cd "$OUT" && sha256sum "stremioproxywan_${VERSION}_all.deb" "stremioproxywan-$VERSION.tar.gz" > SHA256SUMS)
echo "Built $OUT"

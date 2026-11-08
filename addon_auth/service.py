"""Standalone loopback addon service; account proof is checked against Stremio API.

This service deliberately DOES NOT bypass Core authentication. No authKey/passwords are
written to disk, and bearer manifest capabilities may be revoked individually.
"""
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import threading
import urllib.error
import urllib.request

ROOT = Path(os.getenv("STREMIO_ADDON_STATE_DIR", "/var/lib/stremioproxywan-addon"))
HOSTNAME = os.getenv("STREMIO_ADDON_PUBLIC_HOST", "str.lusosolutions.com")
STATE = ROOT / "accounts.json"
LOCK = threading.RLock()
CAPABILITY_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.@:-]{1,256}$")
MAX_BODY = 8192

def load():
    try:
        obj = json.loads(STATE.read_text())
        return obj if isinstance(obj, dict) and isinstance(obj.get("accounts"), dict) and isinstance(obj.get("capabilities"), dict) else {"accounts": {}, "capabilities": {}}
    except (OSError, ValueError):
        return {"accounts": {}, "capabilities": {}}

def save(data):
    ROOT.mkdir(mode=0o770, parents=True, exist_ok=True)
    import tempfile
    fd, name = tempfile.mkstemp(prefix=".accounts-", dir=ROOT)
    try:
        os.fchmod(fd, 0o660)
        import grp
        os.fchown(fd, -1, grp.getgrnam("www-data").gr_gid)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, sort_keys=True)
        os.replace(name, STATE)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def validate_stremio(auth_key, transport=None):
    if not isinstance(auth_key, str) or not (8 <= len(auth_key) <= 4096):
        raise ValueError("invalid credential")
    transport = transport or urllib.request.urlopen
    body = json.dumps({"authKey": auth_key}).encode()
    req = urllib.request.Request("https://api.strem.io/api/getUser", body, headers={"Content-Type": "application/json"}, method="POST")
    with transport(req, timeout=8) as response:
        obj = json.loads(response.read(65536))
    if not isinstance(obj, dict) or obj.get("error") or not isinstance(obj.get("result"), dict):
        raise ValueError("Stremio rejected credential")
    account = obj["result"].get("_id")
    if not isinstance(account, str) or not ACCOUNT_RE.fullmatch(account):
        raise ValueError("invalid account")
    return account

def authorize_account(account):
    if not ACCOUNT_RE.fullmatch(account):
        raise ValueError("Invalid Stremio account id")
    with LOCK:
        state = load()
        state["accounts"][account] = True
        save(state)

def revoke_account(account):
    with LOCK:
        state = load()
        state["accounts"].pop(account, None)
        for digest, assigned in list(state["capabilities"].items()):
            if assigned == account:
                del state["capabilities"][digest]
        save(state)

def grant(account):
    with LOCK:
        state = load()
        if state["accounts"].get(account) is not True:
            return None
        token = secrets.token_urlsafe(32)
        state["capabilities"][hashlib.sha256(token.encode()).hexdigest()] = account
        save(state)
        return token

def verify(token):
    if not CAPABILITY_RE.fullmatch(token):
        return False
    digest = hashlib.sha256(token.encode()).hexdigest()
    with LOCK:
        state = load()
        # Lookup is by digest, never log either the token or the digest.
        account = state["capabilities"].get(digest)
        return bool(account and state["accounts"].get(account) is True)

def manifest():
    return {
        "id": "com.lusosolutions.stremioproxywan.account",
        "version": "0.1.0",
        "name": "StremioProxyWAN Account",
        "description": "Private account-bound access; does not override streaming-server authentication",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "proxywan-account"}],
        "behaviorHints": {"configurable": False},
    }

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # never log credential-bearing URLs
    def reply(self, code, data=None, mime="application/json"):
        body = (json.dumps(data) if mime == "application/json" else data).encode() if data is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
    def do_POST(self):
        if self.path != "/pair":
            return self.reply(404)
        # Nginx must authenticate browser cookie before forwarding this route.
        if self.headers.get("X-ProxyWAN-Authenticated") != "verified":
            return self.reply(403)
        if self.headers.get("Origin", "") != f"https://{HOSTNAME}":
            return self.reply(403)
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self.reply(415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                return self.reply(413)
            data = json.loads(self.rfile.read(size))
            account = validate_stremio(data.get("authKey"))
            token = grant(account)
            if not token:
                return self.reply(403, {"error": "account not authorized", "accountId": account})
            return self.reply(200, {"manifestUrl": f"https://{HOSTNAME}/_addon/{token}/manifest.json", "accountId": account})
        except (ValueError, KeyError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return self.reply(401, {"error": "Stremio account could not be verified"})
    def do_GET(self):
        if self.path == "/configure":
            html = """<!doctype html><html lang="pt"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>StremioProxyWAN Account</title><body><h1>Associar conta Stremio</h1><p>Inicie sessão no WebPlayer deste domínio, depois use esta página. Apenas contas autorizadas podem associar o addon.</p><button id="pair">Associar conta actual</button><p id="msg"></p><script>
document.getElementById('pair').onclick=async()=>{
 const msg=document.getElementById('msg');
 try {
   const profile=JSON.parse(localStorage.getItem('profile')||'null');
   const key=profile&&profile.auth&&(profile.auth.key||profile.auth.authKey);
   if(!key)throw Error('Sessão Stremio não encontrada neste domínio.');
   const r=await fetch('/_addon/pair',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({authKey:key})});
   const x=await r.json();
   if(!r.ok)throw Error('Conta '+(x.accountId||'desconhecida')+' não autorizada ou sessão inválida ('+r.status+').'); const a=document.createElement('a');
   a.href=x.manifestUrl.replace('https://','stremio://');
   a.textContent='Instalar addon privado no Stremio';
   msg.replaceChildren(a);
 }catch(e){msg.textContent=e.message}
};
</script></body></html>"""
            return self.reply(200, html, "text/html; charset=utf-8")
        m = re.fullmatch(r"/([A-Za-z0-9_-]{43})/(manifest\.json|catalog/movie/proxywan-account\.json)", self.path)
        if not m or not verify(m[1]):
            return self.reply(404)
        if m[2] == "manifest.json":
            return self.reply(200, manifest())
        return self.reply(200, {"metas": []})

if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", 18766), Handler).serve_forever()

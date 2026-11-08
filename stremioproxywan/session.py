#!/usr/bin/env python3
"""Loopback-only session issuer for Nginx auth_request. Session secrets never leave host."""
import base64
import hashlib
import hmac
import http.server
import json
import os
import time
from http.cookies import SimpleCookie

KEY_FILE = os.environ.get('STREMIOPROXYWAN_KEY_FILE', '/etc/stremioproxywan/session.key')
SECRET = open(KEY_FILE, 'rb').read().strip()
TTL = 12 * 3600
NAME = 'stremio_proxy_session'

def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def decode(data):
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))

def signature(payload):
    return encode(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def reply(self, code, headers=None):
        self.send_response(code)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        if self.path == '/check':
            try:
                cookies = SimpleCookie()
                cookies.load(self.headers.get('Cookie', ''))
                payload, mac = cookies[NAME].value.rsplit('.', 1)
                expiry = json.loads(decode(payload))['exp']
                now = time.time()
                if hmac.compare_digest(mac, signature(payload)) and now < expiry <= now + TTL + 60:
                    return self.reply(204)
            except (ValueError, KeyError, TypeError, IndexError):
                pass
            return self.reply(401)
        if self.path == '/issue':
            user = self.headers.get('X-Authenticated-User', '')
            if not user or len(user) > 128:
                return self.reply(403)
            payload = encode(json.dumps({'u': user, 'exp': int(time.time()) + TTL}, separators=(',', ':')).encode())
            token = payload + '.' + signature(payload)
            return self.reply(302, {'Set-Cookie': f'{NAME}={token}; Path=/; Max-Age={TTL}; Secure; HttpOnly; SameSite=Lax', 'Location': '/'})
        return self.reply(404)

if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1', 18765), Handler).serve_forever()

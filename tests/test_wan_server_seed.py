"""ProxyWAN must seed the browser to its authenticated origin only."""
import unittest
from stremioproxywan.config import DEFAULTS, nginx_config

class WanSeedTest(unittest.TestCase):
    def test_automatic_webplayer_seed_is_wan_origin(self):
        d={**DEFAULTS, "wan_host":"media.example.org",
           "backend_host":"192.168.1.250",
           "backend_tls_name":"192-168-1-250.519b6502d940.stremio.rocks"}
        conf=nginx_config(d)
        route=conf.split("location = /localStorage.json {",1)[1].split("\n }",1)[0]
        self.assertIn('auth_basic "Stremio - acesso restrito";',route)
        self.assertIn('auth_request /_session/check;',route)
        self.assertIn('proxy_ssl_verify on;',route)
        self.assertIn('proxy_set_header Accept-Encoding "";',route)
        self.assertIn('sub_filter_types application/json;',route)
        self.assertIn(
          "sub_filter 'https://192-168-1-250.519b6502d940.stremio.rocks:12470/' 'https://media.example.org/';",route)
        self.assertIn('Cache-Control "private, no-store"',route)
        self.assertNotIn('auth_basic off;',route)

    def test_nonstandard_wan_port_is_preserved(self):
        d={**DEFAULTS,"wan_host":"media.example.net","wan_port":8443}
        c=nginx_config(d)
        self.assertIn("'https://media.example.net:8443/';",c)

    def test_existing_media_and_addon_controls_are_not_removed(self):
        c=nginx_config(DEFAULTS)
        for route in ('/_addon/pair', '/_media/check', '/_core/check', '/_session/check'):
            self.assertIn(route,c)

if __name__ == "__main__":
    unittest.main()
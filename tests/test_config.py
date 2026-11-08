import unittest
from stremioproxywan.config import DEFAULTS, nginx_config, validate, require_deployment_values
class ConfigTest(unittest.TestCase):
    def test_defaults(self):
        d=validate(DEFAULTS)
        result=nginx_config(d)
        self.assertIn('proxy_ssl_verify on;',result)
        self.assertNotIn('listen 80;',result)
        self.assertIn('http%3A%2F%2Flan.example.invalid%3A11470',result)
        with self.assertRaises(ValueError): require_deployment_values(d)
    def test_custom_host_and_ports(self):
        d={**DEFAULTS,'wan_host':'media.example.org','wan_port':8443,'lan_host':'10.20.30.40','lan_core_port':11500,'backend_host':'backend.example.org','backend_tls_name':'backend.example.org','backend_port':12500,'http_policy':'redirect'}
        result=nginx_config(d)
        self.assertIn('listen 8443 ssl http2;',result)
        self.assertIn('https%3A%2F%2Fmedia\\.example\\.org%3A8443',result)
        self.assertIn('http%3A%2F%2F10.20.30.40%3A11500',result)
        self.assertIn('proxy_pass https://backend.example.org:12500;',result)
        self.assertIn('return 301 https://media.example.org:8443',result)
    def test_legacy_http_opt_in(self):
        self.assertIn('proxy_pass http://lan.example.invalid:8080;',nginx_config({**DEFAULTS,'http_policy':'legacy_proxy'}))
    def test_invalid_host_rejected(self):
        for value in ('good.example;return 200','https://foo','foo\nroot /','../foo'):
            with self.assertRaises(ValueError): validate({**DEFAULTS,'wan_host':value})
    def test_dynamic_wan_ddns(self):
        d={**DEFAULTS,'wan_host':'video.dyndns.org','wan_address_mode':'ddns',
           'lan_host':'10.25.1.50','backend_host':'internal.example.org',
           'backend_tls_name':'internal.example.org'}
        require_deployment_values(validate(d))
        config=nginx_config(d)
        self.assertIn('server_name video.dyndns.org;',config)
        self.assertNotIn('192.168.1.199',config)
        self.assertIn('http%3A%2F%2F10.25.1.50%3A11470',config)
    def test_direct_wan_ipv4(self):
        config=nginx_config({**DEFAULTS,'wan_host':'203.0.113.15','wan_address_mode':'direct_ip'})
        self.assertIn('server_name 203.0.113.15;',config)
        with self.assertRaises(ValueError):
            validate({**DEFAULTS,'wan_host':'video.dyndns.org','wan_address_mode':'direct_ip'})
    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError): validate({**DEFAULTS,'wan_port':77777})
if __name__=='__main__': unittest.main()

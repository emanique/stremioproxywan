"""Regression tests for fixed-LAN deployment, auto TLS discovery and safe CLI."""
import unittest
from unittest.mock import patch

from stremioproxywan import cli
from stremioproxywan.config import DEFAULTS, nginx_config


class FixedLANIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.settings = {
            **DEFAULTS,
            'wan_host': 'media.example.net',
            'lan_host': '192.168.1.199',
            'backend_identity_mode': 'stremio_auto',
            'backend_port': 12470,
            'backend_scheme': 'https',
        }

    @patch('stremioproxywan.cli.discover_backend')
    def test_auto_discovers_from_fixed_lan_ip(self, discovery):
        discovery.return_value = ('192.168.1.199', '192-168-1-199.519b6502d940.stremio.rocks')
        resolved = cli.effective_backend(self.settings)
        discovery.assert_called_once_with(
            '192.168.1.199', 12470, '/etc/ssl/certs/ca-certificates.crt')
        rendered = nginx_config(resolved)
        self.assertIn('proxy_pass https://192.168.1.199:12470;', rendered)
        self.assertIn('proxy_ssl_name 192-168-1-199.519b6502d940.stremio.rocks;', rendered)
        self.assertIn('proxy_ssl_verify on;', rendered)
        self.assertEqual(self.settings['lan_host'], '192.168.1.199')

    @patch('stremioproxywan.cli.discover_backend')
    def test_changed_wildcard_is_used_without_changing_lan_ip(self, discovery):
        discovery.return_value = ('192.168.1.199', '192-168-1-199.new-cert.stremio.rocks')
        resolved = cli.effective_backend(self.settings)
        self.assertEqual(resolved['backend_host'], '192.168.1.199')
        self.assertEqual(resolved['backend_tls_name'], '192-168-1-199.new-cert.stremio.rocks')

    @patch('stremioproxywan.cli.discover_backend')
    def test_invalid_certificate_stops_rendering(self, discovery):
        from stremioproxywan.discovery import DiscoveryError
        discovery.side_effect = DiscoveryError('TLS certificate validation failed')
        with self.assertRaises(DiscoveryError):
            cli.effective_backend(self.settings)

    @patch('stremioproxywan.cli.discover_backend')
    def test_manual_mode_does_not_probe(self, discovery):
        settings = {
            **self.settings,
            'backend_identity_mode': 'manual',
            'backend_host': 'internal.example.org',
            'backend_tls_name': 'internal.example.org',
        }
        self.assertEqual(cli.effective_backend(settings), settings)
        discovery.assert_not_called()


if __name__ == '__main__':
    unittest.main()

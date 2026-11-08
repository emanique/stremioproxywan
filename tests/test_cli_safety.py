"""Safety boundaries: never change Nginx if backend identity cannot be verified."""
import unittest
from unittest.mock import patch

from stremioproxywan import cli
from stremioproxywan.config import DEFAULTS
from stremioproxywan.discovery import DiscoveryError


class ApplySafetyTests(unittest.TestCase):
    @patch('stremioproxywan.cli.run')
    @patch('stremioproxywan.cli.backup')
    @patch('stremioproxywan.cli.TARGET')
    @patch('stremioproxywan.cli.generate_selfsigned')
    @patch('stremioproxywan.cli.ensure_secret')
    @patch('stremioproxywan.cli.ensure_users')
    @patch('stremioproxywan.cli.permissions')
    @patch('stremioproxywan.cli.preflight')
    @patch('stremioproxywan.cli.load')
    @patch('stremioproxywan.cli.root_only')
    @patch('stremioproxywan.cli.discover_backend')
    def test_tls_discovery_failure_does_not_modify_nginx(
        self, discover, root_only, load, preflight, permissions, users, secret,
        cert, target, backup, run,
    ):
        load.return_value = {
            **DEFAULTS,
            'wan_host': 'media.example.net',
            'lan_host': '192.168.1.199',
        }
        discover.side_effect = DiscoveryError('certificate not trusted')

        with self.assertRaises(DiscoveryError):
            cli.apply()

        target.write_text.assert_not_called()
        target.write_bytes.assert_not_called()
        backup.assert_not_called()
        run.assert_not_called()

    @patch('stremioproxywan.cli.discover_backend')
    def test_no_background_ip_reconciliation_in_cli(self, discover):
        settings = {
            **DEFAULTS,
            'wan_host': 'media.example.net',
            'lan_host': '192.168.1.199',
        }
        discover.return_value = (
            '192.168.1.199',
            '192-168-1-199.example.stremio.rocks',
        )
        resolved = cli.effective_backend(settings)
        self.assertEqual(settings['lan_host'], '192.168.1.199')
        self.assertEqual(resolved['backend_host'], '192.168.1.199')


if __name__ == '__main__':
    unittest.main()

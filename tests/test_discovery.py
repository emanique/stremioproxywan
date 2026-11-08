import unittest
from unittest.mock import patch

from stremioproxywan.discovery import DiscoveryError, candidate_from_sans, discover_backend


class DiscoveryTest(unittest.TestCase):
    def test_stremio_wildcard_ip_derived_identity(self):
        name = candidate_from_sans('192.168.1.199', ['*.519b6502d940.stremio.rocks'])
        self.assertEqual(name, '192-168-1-199.519b6502d940.stremio.rocks')

    def test_changed_ip_changes_tls_identity(self):
        san = ['*.519b6502d940.stremio.rocks']
        old = candidate_from_sans('192.168.1.199', san)
        new = candidate_from_sans('192.168.1.230', san)
        self.assertNotEqual(old, new)
        self.assertEqual(new, '192-168-1-230.519b6502d940.stremio.rocks')

    def test_certificate_suffix_changes(self):
        self.assertEqual(
            candidate_from_sans('10.10.0.20', ['*.newidentity.stremio.rocks']),
            '10-10-0-20.newidentity.stremio.rocks',
        )

    def test_exact_dns_san(self):
        self.assertEqual(
            candidate_from_sans('10.10.0.20', ['stremio.internal.example']),
            'stremio.internal.example',
        )

    def test_reject_missing_san(self):
        with self.assertRaises(DiscoveryError):
            candidate_from_sans('10.10.0.20', ['*.bad_domain.example'])

    @patch('stremioproxywan.discovery._san_names', return_value=['*.new.stremio.rocks'])
    @patch('stremioproxywan.discovery._resolve_ipv4', return_value='10.10.1.25')
    @patch('stremioproxywan.discovery.ssl.create_default_context')
    @patch('stremioproxywan.discovery.socket.create_connection')
    def test_verifies_discovered_identity(self, connection, context, resolver, sans):
        target, name = discover_backend('stremio.lan', 12470, '/private/ca.pem')
        self.assertEqual((target, name), ('10.10.1.25', '10-10-1-25.new.stremio.rocks'))
        context.assert_called_once_with(cafile='/private/ca.pem')
        context.return_value.wrap_socket.assert_called_once()
        self.assertEqual(context.return_value.wrap_socket.call_args.kwargs['server_hostname'], name)

    @patch('stremioproxywan.discovery._san_names', return_value=['*.new.stremio.rocks'])
    @patch('stremioproxywan.discovery._resolve_ipv4', return_value='10.10.1.25')
    @patch('stremioproxywan.discovery.ssl.create_default_context')
    @patch('stremioproxywan.discovery.socket.create_connection')
    def test_fails_closed_on_invalid_tls(self, connection, context, resolver, sans):
        import ssl
        context.return_value.wrap_socket.side_effect = ssl.SSLCertVerificationError('untrusted')
        with self.assertRaises(DiscoveryError):
            discover_backend('stremio.lan', 12470, '/private/ca.pem')


if __name__ == '__main__':
    unittest.main()

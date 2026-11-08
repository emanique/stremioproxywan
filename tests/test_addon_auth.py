import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from addon_auth import service
from stremioproxywan.config import nginx_config, DEFAULTS

class AccountAddonTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.state_patch = patch.object(service, "ROOT", Path(self.dir.name))
        self.file_patch = patch.object(service, "STATE", Path(self.dir.name) / "accounts.json")
        self.state_patch.start()
        self.file_patch.start()
        self.addCleanup(self.state_patch.stop)
        self.addCleanup(self.file_patch.stop)

    def test_denied_until_allowlist(self):
        self.assertIsNone(service.grant("user-1"))

    def test_private_manifest_and_revocation(self):
        service.authorize_account("user-1")
        token = service.grant("user-1")
        self.assertTrue(service.verify(token))
        self.assertFalse(service.verify(token + "A"))
        self.assertFalse(service.verify("z" * 43))
        self.assertNotIn(token, service.STATE.read_text())
        service.revoke_account("user-1")
        self.assertFalse(service.verify(token))

    def test_unknown_bad_account(self):
        with self.assertRaises(ValueError):
            service.authorize_account("../../etc/passwd")

    def test_addon_cors_only_public_resource_routes(self):
        conf = nginx_config(DEFAULTS)
        resource_location = conf.split('location ~ "^/_addon/')[1].split('location = /login')[0]
        self.assertIn('Access-Control-Allow-Origin "*"', resource_location)
        self.assertIn('GET, HEAD, OPTIONS', resource_location)
        pairing = conf.split('location = /_addon/pair')[1].split('location ~ "^/_addon/')[0]
        self.assertNotIn('Access-Control-Allow-Origin "*"', pairing)
        self.assertIn('auth_request /_session/check', pairing)

    def test_manifest_protocol(self):
        item = service.manifest()
        self.assertEqual(item["resources"], ["catalog"])
        self.assertEqual(item["catalogs"][0]["id"], "proxywan-account")

    def test_stremio_invalid_json_response(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self, n): return b'{"error":{"code":1}}'
        with self.assertRaises(ValueError):
            service.validate_stremio("valid-format-token", transport=lambda *a, **k: Response())

    def test_stremio_user_id(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self, n): return b'{"result":{"_id":"user-123","email":"x@example.invalid"}}'
        self.assertEqual(service.validate_stremio("valid-format-token", transport=lambda *a, **k: Response()), "user-123")

if __name__ == "__main__":
    unittest.main()

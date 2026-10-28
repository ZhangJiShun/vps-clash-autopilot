"""Synthetic privacy regression; no real account data."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_check import scan_text

class PrivacyTests(unittest.TestCase):
    def test_documentation_addresses_allowed(self):
        self.assertEqual(scan_text('192.0.2.10 2001:db8::2 127.0.0.1 ::1 0.0.0.0'), [])

    def test_real_looking_addresses_and_personal_fields_rejected(self):
        for text in ['8.8.' + '8.8', ':'.join(['2001', '4860', '4860', '', '8888']), '/Users/' + 'example/private', 'person' + '@example.org', '-----BEGIN ' + 'PRIVATE KEY-----']:
            self.assertTrue(scan_text(text))

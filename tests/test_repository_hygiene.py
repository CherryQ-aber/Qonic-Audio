from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_repository_hygiene import scan_path, scan_repository, scan_text


class RepositoryHygieneTests(unittest.TestCase):
    def test_current_repository_inputs_pass(self):
        self.assertEqual(scan_repository(ROOT), [])

    def test_local_only_paths_are_rejected_without_harming_test_code(self):
        self.assertTrue(scan_path("Codex_memory/session.md"))
        self.assertTrue(scan_path(".codex/config.toml"))
        self.assertTrue(scan_path("Cache/runtime.json"))
        self.assertTrue(scan_path("build/Qonic.exe"))
        self.assertTrue(scan_path("Test_Files/real-track.flac"))
        self.assertEqual(scan_path("tests/test_audio_logic.py"), [])
        self.assertEqual(scan_path("Test_Files/README.md"), [])

    def test_compliance_evidence_archives_are_narrowly_allowed(self):
        self.assertEqual(
            scan_path("docs/compliance/staging/artifacts/wheels/example.whl"),
            [],
        )
        self.assertTrue(scan_path("downloads/example.whl"))

    def test_private_identity_is_never_whitelisted(self):
        private_email = "316983335" + "@" + "qq.com"
        owner_path = "\\".join(("C:", "Users", "Cherry Q", "project"))
        fixture = "tests/fixtures/synthetic_privacy/private_identity.txt"
        self.assertTrue(scan_text(fixture, private_email))
        self.assertTrue(scan_text(fixture, owner_path))

    def test_synthetic_fixture_suppresses_only_fake_pattern_noise(self):
        fixture_path = (
            ROOT
            / "tests"
            / "fixtures"
            / "synthetic_privacy"
            / "synthetic_sensitive_patterns.txt"
        )
        text = fixture_path.read_text(encoding="utf-8")
        self.assertEqual(scan_text(fixture_path.relative_to(ROOT), text), [])
        self.assertTrue(scan_text("docs/copied_fixture.txt", text))
        unapproved_token = "ghp_" + "z" * 36
        self.assertTrue(
            scan_text(fixture_path.relative_to(ROOT), unapproved_token)
        )

    def test_non_placeholder_credentials_are_rejected(self):
        assignment = "api" + '_key = "live-looking-value-123"'
        credential_url = "https://account:" + "credential@example.invalid"
        self.assertTrue(
            scan_text("config/public.py", assignment)
        )
        self.assertTrue(
            scan_text("docs/url.txt", credential_url)
        )
        self.assertEqual(
            scan_text("config/example.py", 'api_key = "replace_me"'),
            [],
        )


if __name__ == "__main__":
    unittest.main()

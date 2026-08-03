from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from collect_ffmpeg_info import collect_ffmpeg
from build_compliance_bundle import _contains_forbidden_content
from common import ComplianceError
from validate_compliance import evaluate_exit_code, validate_final_inventory_data
from verify_ncmdump_asset import compare_ncmdump_asset, safe_extract_zip
from verify_ffmpeg_asset import parse_archive_paths


class ValidationTests(unittest.TestCase):

    def test_streaming_privacy_scan_detects_cross_chunk_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large.bin"
            path.write_bytes(
                b"A" * (1024 * 1024 - 5)
                + b"C:\\Users\\Example User\\private"
            )
            self.assertTrue(_contains_forbidden_content(path))

    def test_privacy_scan_does_not_treat_ask_learn_as_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "documentation.html"
            path.write_text(
                'data-test-id="ask-learn-assistant-modal-entry-mobile"',
                encoding="utf-8",
            )
            self.assertFalse(_contains_forbidden_content(path))

    def test_safe_zip_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "asset.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("../escape.exe", b"bad")
            with self.assertRaises(ComplianceError):
                safe_extract_zip(archive, root / "out")
            self.assertFalse((root / "escape.exe").exists())

    def test_ncmdump_hash_match_and_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "ncmdump.exe"
            local.write_bytes(b"same-binary")
            matching = root / "matching.zip"
            with zipfile.ZipFile(matching, "w") as stream:
                stream.writestr("ncmdump.exe", b"same-binary")
            different = root / "different.zip"
            with zipfile.ZipFile(different, "w") as stream:
                stream.writestr("ncmdump.exe", b"different-binary")
            self.assertTrue(
                compare_ncmdump_asset(local, matching)[
                    "byte_identical_to_upstream"
                ]
            )
            self.assertFalse(
                compare_ncmdump_asset(local, different)[
                    "byte_identical_to_upstream"
                ]
            )
            self.assertEqual(
                compare_ncmdump_asset(local, different)["status"],
                "BINARY_MISMATCH",
            )

    def test_ncmdump_library_asset_is_not_treated_as_cli_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "ncmdump.exe"
            local.write_bytes(b"cli-binary")
            library_asset = root / "libncmdump.zip"
            with zipfile.ZipFile(library_asset, "w") as stream:
                stream.writestr("libncmdump.dll", b"library-binary")
            result = compare_ncmdump_asset(local, library_asset)
            self.assertEqual(result["status"], "ASSET_TYPE_MISMATCH")
            self.assertFalse(result["byte_identical_to_upstream"])
            self.assertEqual(result["asset_members"][0]["path"], "libncmdump.dll")

    def test_ffmpeg_7zip_listing_parser_skips_archive_header(self):
        listing = "\n".join(
            [
                "Path = ffmpeg-8.1.1-full_build.7z",
                "Type = 7z",
                "Path = ffmpeg-8.1.1-full_build/bin/ffmpeg.exe",
                "Size = 10",
                "Path = ffmpeg-8.1.1-full_build/bin/ffprobe.exe",
                "Size = 11",
            ]
        )
        self.assertEqual(
            parse_archive_paths(listing),
            [
                "ffmpeg-8.1.1-full_build/bin/ffmpeg.exe",
                "ffmpeg-8.1.1-full_build/bin/ffprobe.exe",
            ],
        )

    def test_missing_ffmpeg_is_reported_without_silent_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dist = root / "dist"
            output = root / "report"
            dist.mkdir()
            result = collect_ffmpeg(root, dist, output)
            self.assertEqual(result["files"]["files"], [])
            self.assertIn("未找到 ffmpeg.exe", result["files"]["failures"])

    def test_exit_code_mapping(self):
        self.assertEqual(
            evaluate_exit_code({"blockers": [], "warnings": []}, [], []),
            0,
        )
        self.assertEqual(
            evaluate_exit_code(
                {"blockers": [], "warnings": [{"code": "W"}]},
                [],
                [],
            ),
            1,
        )
        self.assertEqual(
            evaluate_exit_code(
                {"blockers": [{"code": "B"}], "warnings": []},
                [],
                [],
            ),
            2,
        )

    def test_final_inventory_rejects_unknown_native_component(self):
        component = {
            "component": "Microsoft VC Runtime",
            "component_type": "runtime-dll",
            "version": "14.x",
            "source_package": "Visual Studio 2026 REDIST",
            "upstream_project": "Microsoft",
            "package_provenance": {"evidence": "test"},
            "files": ["_internal/VCRUNTIME140.dll"],
            "hashes": {"_internal/VCRUNTIME140.dll": "A" * 64},
            "license": "Microsoft terms",
            "license_files": ["docs/compliance/staging/licenses/Microsoft/test.txt"],
            "redistribution_requirement": "unmodified",
            "notice_requirement": "record terms",
            "source_code_availability": "https://example.invalid",
            "compliance_status": "CLOSED",
        }
        inventory = {
            "schema_version": "1.0.0",
            "generated_on": "2026-08-03",
            "identity_algorithm": "SHA-256",
            "authoritative_release": {"archive_sha256": "B" * 64},
            "components": [component],
            "native_file_ownership": {
                "unassigned_native_files": ["_internal/mystery.dll"]
            },
            "summary": {},
        }
        errors, _ = validate_final_inventory_data(inventory)
        self.assertTrue(any("UNKNOWN THIRD-PARTY COMPONENT" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

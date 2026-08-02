from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from collect_ffmpeg_info import (
    match_configure_flags_to_versions,
    parse_build_configuration,
    parse_package_dependency_versions,
)
from collect_qt_inventory import qt_license_status, qt_source_module
from collect_qt_upstream_info import parse_mirrorlist
from common import required_component_fields
from generate_manifest import _is_msvc_runtime_file, _runtime_identity
from validate_compliance import validate_manifest_data


def make_component() -> dict:
    component = {field: None for field in required_component_fields()}
    component.update(
        {
            "name": "Example",
            "category": "test",
            "bundled_files": ["DIST/example.dll"],
            "binary_sha256": {"DIST/example.dll": "A" * 64},
            "byte_identical_to_upstream": None,
            "evidence_files": [],
            "unresolved_questions": [],
            "license_status": "VERIFIED",
        }
    )
    return component


def make_manifest() -> dict:
    return {
        "schema_version": "1.0.0",
        "product": {
            "name": "Qonic Audio",
            "version": "5.0 Internal Test",
            "repository_license": "GPL-3.0-or-later",
        },
        "generated_at": "2026-07-24T00:00:00+00:00",
        "identity_algorithm": "SHA-256",
        "components": [make_component()],
        "findings": [],
        "blockers": [],
        "warnings": [],
        "manual_decisions_required": [],
    }


class ManifestTests(unittest.TestCase):

    def test_gyan_package_dependency_versions_are_parsed(self):
        readme = """header
release-full external libraries' versions:

x264 v0.165.3223
openal-soft latest
"""
        self.assertEqual(
            parse_package_dependency_versions(readme),
            {
                "x264": "v0.165.3223",
                "openal-soft": "latest",
            },
        )

    def test_gyan_configure_flags_match_version_aliases(self):
        matched, missing = match_configure_flags_to_versions(
            ["--enable-libx264", "--enable-libmp3lame", "--enable-fontconfig"],
            {"x264": "v0.165.3223", "lame": "3.100"},
        )
        self.assertEqual(matched["--enable-libx264"]["dependency"], "x264")
        self.assertEqual(matched["--enable-libmp3lame"]["dependency"], "lame")
        self.assertEqual(missing, ["--enable-fontconfig"])

    def test_schema_file_is_valid_json_and_names_qonic(self):
        schema = json.loads(
            (TOOL_ROOT / "schemas" / "third_party_manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["properties"]["product"]["properties"]["name"]["const"],
            "Qonic Audio",
        )

    def test_minimal_manifest_passes_structural_validation(self):
        errors, warnings = validate_manifest_data(make_manifest())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_old_product_name_is_rejected(self):
        manifest = make_manifest()
        manifest["product"]["name"] = "CherryQ Audio Converter"
        errors, _ = validate_manifest_data(manifest)
        self.assertTrue(any("旧项目名称" in error for error in errors))

    def test_invalid_sha256_is_rejected(self):
        manifest = make_manifest()
        manifest["components"][0]["binary_sha256"]["DIST/example.dll"] = "bad"
        errors, _ = validate_manifest_data(manifest)
        self.assertTrue(any("非法 SHA-256" in error for error in errors))

    def test_ffmpeg_configuration_classification(self):
        gpl = parse_build_configuration(
            "ffmpeg version 8.1.1\nconfiguration: --enable-gpl --enable-version3"
        )
        self.assertEqual(gpl["classification"], "FFmpeg-GPL-CANDIDATE")
        nonfree = parse_build_configuration(
            "configuration: --enable-gpl --enable-nonfree"
        )
        self.assertEqual(nonfree["classification"], "FFmpeg-NONFREE-BLOCKER")
        lgpl = parse_build_configuration("configuration: --enable-static")
        self.assertEqual(lgpl["classification"], "FFmpeg-LGPL-CANDIDATE")

    def test_qt_module_mapping_and_gpl_risk(self):
        self.assertEqual(qt_source_module("Qt6Core.dll"), "qtbase")
        self.assertEqual(qt_source_module("Qt6Qml.dll"), "qtdeclarative")
        self.assertEqual(
            qt_license_status("Qt6VirtualKeyboard.dll"),
            "GPL-ONLY-RISK",
        )
        self.assertEqual(
            qt_source_module("Qt6WebEngineCore.dll"),
            "qtwebengine",
        )
        self.assertEqual(
            qt_source_module("Qt63DCore.dll"),
            "qt3d",
        )

    def test_qt_mirrorlist_parser(self):
        payload = parse_mirrorlist(
            """
            Filename: qtbase-everywhere-src-6.11.1.tar.xz
            Size: 48M (50648500 bytes)
            Last modified: Tue, 12 May 2026 04:38:35 GMT (Unix time: 1)
            SHA-256 Hash : d9594a31228aa23ad6b531719a29b45f0f3989fe6c136d45767ea179f233c1ac
            """
        )
        self.assertEqual(payload["size"], 50648500)
        self.assertEqual(
            payload["sha256"],
            "D9594A31228AA23AD6B531719A29B45F0F3989FE6C136D45767EA179F233C1AC",
        )

    def test_runtime_identity_matches_dist_and_release_paths(self):
        self.assertEqual(
            _runtime_identity(
                "Release/build/Qonic/_internal/PySide6/MSVCP140.dll"
            ),
            _runtime_identity("DIST/_internal/PySide6/MSVCP140.dll"),
        )

    def test_msvc_runtime_name_detection_covers_full_onedir_scope(self):
        self.assertTrue(_is_msvc_runtime_file(Path("MSVCP140.dll")))
        self.assertTrue(
            _is_msvc_runtime_file(Path("msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll"))
        )
        self.assertTrue(_is_msvc_runtime_file(Path("VCRUNTIME140_1.dll")))
        self.assertTrue(_is_msvc_runtime_file(Path("vc_redist.x64.exe")))
        self.assertFalse(_is_msvc_runtime_file(Path("Qt6Core.dll")))
        self.assertFalse(_is_msvc_runtime_file(Path("cl.exe")))


if __name__ == "__main__":
    unittest.main()

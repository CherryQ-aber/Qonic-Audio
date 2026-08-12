import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InternalBetaGovernanceTests(unittest.TestCase):
    def test_current_status_sources_define_internal_beta(self):
        status = (ROOT / "docs" / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        policy = (ROOT / "docs" / "RELEASE_STRATEGY.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in (status, policy, readme):
            self.assertIn("Internal Beta", text)
            self.assertIn("Personal Software Project", text)
        self.assertIn("Pre-release", policy)
        self.assertIn("DEFERRED — PUBLIC RELEASE ONLY", policy)
        self.assertIn("Brand: NOT FROZEN", status)
        self.assertIn("Qonance: NOT ADOPTED", status)

    def test_installer_contract_wraps_onedir_and_preserves_user_data(self):
        installer = (
            ROOT / "installer" / "Qonic_Audio_Internal_Beta.iss"
        ).read_text(encoding="utf-8")
        chinese_messages = (
            ROOT / "installer" / "languages" / "ChineseSimplified.isl"
        ).read_text(encoding="utf-8")
        inno_license = (
            ROOT / "LICENSES" / "Inno-Setup-License.txt"
        ).read_text(encoding="utf-8")
        build_script = (ROOT / "build_installer.ps1").read_text(encoding="utf-8")

        self.assertIn("DefaultDirName={autopf}", installer)
        self.assertIn("{autoprograms}", installer)
        self.assertIn("{autodesktop}", installer)
        self.assertIn("Tasks: desktopicon", installer)
        self.assertIn("UninstallDisplayIcon", installer)
        self.assertNotIn("[UninstallDelete]", installer)
        self.assertIn("LanguageDetectionMethod=uilanguage", installer)
        self.assertIn("ShowLanguageDialog=no", installer)
        self.assertIn("UsePreviousLanguage=no", installer)
        self.assertIn('Name: "en"; MessagesFile: "compiler:Default.isl"', installer)
        self.assertIn(
            'Name: "zhcn"; MessagesFile: "languages\\ChineseSimplified.isl"',
            installer,
        )
        self.assertIn("{cm:CreateDesktopIcon}", installer)
        self.assertIn("{cm:AdditionalIcons}", installer)
        self.assertIn("{cm:LaunchProgram,{#AppDisplayName}}", installer)
        self.assertIn("LICENSES\\Inno-Setup-License.txt", installer)
        self.assertIn("LanguageName=简体中文", chinese_messages)
        self.assertIn("LanguageID=$0804", chinese_messages)
        self.assertIn("CreateDesktopIcon=创建桌面快捷方式", chinese_messages)
        self.assertIn("LaunchProgram=运行 %1", chinese_messages)
        self.assertIn("Copyright (C) 1997-2026 Jordan Russell", inno_license)
        self.assertIn("APP_PACKAGE_BASENAME", build_script)
        self.assertIn("Internal Beta", build_script)
        self.assertIn("ApplicationSource", build_script)
        self.assertIn("Internal_Beta_Candidates", build_script)
        self.assertIn("No verified Internal Beta application candidate found", build_script)
        self.assertIn("Inno Setup 6 compiler not found", build_script)
        self.assertIn("Programs\\Inno Setup 6\\ISCC.exe", build_script)
        self.assertIn("SHA256SUMS.txt", build_script)
        self.assertIn("subst.exe", build_script)
        self.assertNotIn("/DAppVersionNumeric=5.0.0.1", build_script)

    def test_frozen_paths_use_local_app_data_and_migrate_legacy_config_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            program_dir = temp_root / "Program Files" / "Qonic Audio"
            local_app_data = temp_root / "LocalAppData"
            program_dir.mkdir(parents=True)
            legacy_config = program_dir / "config.json"
            legacy_config.write_text(
                json.dumps(
                    {
                        "output_folder": str(program_dir / "Music_Output"),
                        "editor_output_folder": str(
                            program_dir / "AudioEditor_Output"
                        ),
                        "editor_temp_folder": str(program_dir / "Temp" / "Editor"),
                        "target_format": "flac",
                    }
                ),
                encoding="utf-8",
            )

            probe = """
import json, os, sys
sys.frozen = True
sys.executable = os.environ['QONIC_TEST_EXE']
import config
data = config.load_config()
print(json.dumps({
    'app_dir': config.APP_DIR,
    'user_data_dir': config.USER_DATA_DIR,
    'config_file': config.CONFIG_FILE,
    'log_dir': config.LOG_DIR,
    'cache_dir': config.CACHE_DIR,
    'temp_dir': config.TEMP_DIR,
    'output_folder': data['output_folder'],
    'editor_output_folder': data['editor_output_folder'],
    'target_format': data['target_format'],
}))
"""
            env = os.environ.copy()
            env["LOCALAPPDATA"] = str(local_app_data)
            env["QONIC_USER_DATA_ROOT"] = str(local_app_data / "Qonic Audio")
            env["QONIC_TEST_EXE"] = str(program_dir / "Qonic.exe")
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            expected_data_root = local_app_data / "Qonic Audio"

            self.assertEqual(Path(payload["user_data_dir"]), expected_data_root)
            self.assertEqual(Path(payload["config_file"]).parent, expected_data_root / "Config")
            self.assertEqual(Path(payload["log_dir"]), expected_data_root / "Logs")
            self.assertEqual(Path(payload["cache_dir"]).parent, expected_data_root)
            self.assertEqual(Path(payload["temp_dir"]).parent, expected_data_root / "Cache")
            self.assertNotEqual(
                os.path.normcase(payload["output_folder"]),
                os.path.normcase(str(program_dir / "Music_Output")),
            )
            self.assertEqual(payload["target_format"], "flac")
            self.assertTrue((expected_data_root / "Config" / "config.json").is_file())
            self.assertEqual(legacy_config.read_text(encoding="utf-8").strip()[0], "{")


if __name__ == "__main__":
    unittest.main()

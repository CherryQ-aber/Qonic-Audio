import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect

import config
from ui_next.bridge.capabilities import CapabilityGate
from ui_next.bridge.first_run_viewmodel import FirstRunViewModel
from ui_next.bridge.settings_viewmodel import SettingsViewModel
from ui_next.bridge.window_controller import (
    resolve_window_geometry,
    serialize_window_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class IsolatedConfigMixin:
    def isolated_config(self, root: Path, legacy_files=()):
        target = root / "profile" / "Config" / "config.json"
        return (
            patch.object(config, "CONFIG_FILE", str(target)),
            patch.object(
                config,
                "LEGACY_CONFIG_FILES",
                tuple(str(path) for path in legacy_files),
            ),
        )


class ConfigPathAndPersistenceTests(IsolatedConfigMixin, unittest.TestCase):
    def test_frozen_config_path_never_uses_executable_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exe_dir = root / "Program Files" / "Qonic Audio"
            user_root = root / "User Data" / "Qonic Audio"
            code = "\n".join(
                (
                    "import json, os, sys",
                    "sys.frozen = True",
                    f"sys.executable = {str(exe_dir / 'Qonic.exe')!r}",
                    f"os.environ['QONIC_USER_DATA_ROOT'] = {str(user_root)!r}",
                    "import config",
                    "print(json.dumps({'app': config.APP_DIR, 'config': config.CONFIG_FILE, 'cache': config.CACHE_DIR, 'logs': config.LOG_DIR}))",
                )
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            values = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(os.path.normcase(values["app"]), os.path.normcase(str(exe_dir)))
            self.assertFalse(
                os.path.commonpath([values["config"], str(exe_dir)]) == str(exe_dir)
            )
            self.assertIn(os.path.join("Config", "config.json"), values["config"])
            self.assertNotEqual(values["config"], values["cache"])
            self.assertNotEqual(values["cache"], values["logs"])

    def test_save_reload_and_default_merge_preserve_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_patch, legacy_patch = self.isolated_config(root)
            with config_patch, legacy_patch:
                saved = config.save_config(
                    {"theme_mode": "dark", "legacy_field": "keep"}
                )
                reloaded = config.load_config()
            self.assertEqual(saved["theme_mode"], "dark")
            self.assertEqual(reloaded["theme_mode"], "dark")
            self.assertEqual(reloaded["legacy_field"], "keep")
            self.assertIn("window_state", reloaded)
            self.assertIn("watch_folder", reloaded)

    def test_legacy_migration_is_one_time_non_destructive_and_marks_existing_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "install" / "config.json"
            legacy.parent.mkdir(parents=True)
            original = {
                "watch_folder": "D:/CloudMusic/VipSongsDownload",
                "theme_mode": "purple",
                "unknown_setting": 42,
            }
            legacy_bytes = json.dumps(original, ensure_ascii=False).encode("utf-8")
            legacy.write_bytes(legacy_bytes)
            config_patch, legacy_patch = self.isolated_config(root, (legacy,))
            with config_patch, legacy_patch:
                migrated = config.load_config()
                target = Path(config.CONFIG_FILE)
                first_bytes = target.read_bytes()
                second = config.load_config()
            self.assertTrue(target.exists())
            self.assertEqual(legacy.read_bytes(), legacy_bytes)
            self.assertEqual(target.read_bytes(), first_bytes)
            self.assertEqual(migrated["theme_mode"], "purple")
            self.assertEqual(migrated["unknown_setting"], 42)
            self.assertTrue(migrated["first_launch_completed"])
            self.assertEqual(second, migrated)

    def test_atomic_save_failure_is_not_silent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_patch, legacy_patch = self.isolated_config(root)
            with (
                config_patch,
                legacy_patch,
                patch.object(
                    config,
                    "_write_config_atomic",
                    side_effect=OSError("read only"),
                ),
            ):
                with self.assertRaises(OSError):
                    config.save_config({"theme_mode": "dark"})


class ThemeAndFirstRunTests(IsolatedConfigMixin, unittest.TestCase):
    @staticmethod
    def live_gate():
        return CapabilityGate.from_environment({"QONIC_QML_USER_TEST": "1"})

    def test_dark_and_light_survive_view_model_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_patch, legacy_patch = self.isolated_config(root)
            with config_patch, legacy_patch:
                config.save_config(config.DEFAULT_CONFIG)
                for theme in ("dark", "light", "black", "purple", "system"):
                    first = SettingsViewModel(capability_gate=self.live_gate())
                    self.assertTrue(first.applyThemeMode(theme))
                    restarted = SettingsViewModel(capability_gate=self.live_gate())
                    self.assertEqual(restarted.themeMode, theme)

    def test_theme_save_failure_is_exposed_and_not_reported_as_success(self):
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(config.DEFAULT_CONFIG),
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.update_config",
                side_effect=OSError("permission denied"),
            ),
        ):
            view_model = SettingsViewModel(capability_gate=self.live_gate())
            self.assertFalse(view_model.applyThemeMode("dark"))
            self.assertIn("主题保存失败", view_model.saveStatus)

    def test_new_profile_requires_first_run_and_skip_is_durable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_patch, legacy_patch = self.isolated_config(root)
            with config_patch, legacy_patch, patch(
                "ui_next.bridge.first_run_viewmodel.find_watch_folder_candidates",
                return_value=[],
            ):
                self.assertFalse(config.load_config()["first_launch_completed"])
                first = FirstRunViewModel(capability_gate=self.live_gate())
                self.assertTrue(first.required)
                self.assertTrue(first.skip())
                self.assertFalse(first.required)
                restarted = FirstRunViewModel(capability_gate=self.live_gate())
                self.assertFalse(restarted.required)

    def test_accepting_candidate_only_saves_directory_and_first_run_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate = root / "CloudMusic" / "VipSongsDownload"
            candidate.mkdir(parents=True)
            config_patch, legacy_patch = self.isolated_config(root)
            with config_patch, legacy_patch, patch(
                "ui_next.bridge.first_run_viewmodel.find_watch_folder_candidates",
                return_value=[str(candidate)],
            ):
                first = FirstRunViewModel(capability_gate=self.live_gate())
                self.assertEqual(first.candidateCount, 1)
                self.assertTrue(first.useSelectedDirectory())
                persisted = config.load_config()
            self.assertEqual(persisted["watch_folder"], str(candidate))
            self.assertTrue(persisted["first_launch_completed"])
            source = (PROJECT_ROOT / "ui_next/bridge/first_run_viewmodel.py").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("start_monitor", source)
            self.assertNotIn("start_convert", source)

    def test_multiple_candidates_require_an_explicit_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path = root / "D" / "VipSongsDownload"
            second_path = root / "E" / "VipSongsDownload"
            first_path.mkdir(parents=True)
            second_path.mkdir(parents=True)
            config_patch, legacy_patch = self.isolated_config(root)
            with config_patch, legacy_patch, patch(
                "ui_next.bridge.first_run_viewmodel.find_watch_folder_candidates",
                return_value=[str(first_path), str(second_path)],
            ):
                first_run = FirstRunViewModel(capability_gate=self.live_gate())
                self.assertEqual(first_run.candidateCount, 2)
                self.assertEqual(first_run.selectedPath, "")
                first_run.selectCandidate(str(second_path))
                self.assertTrue(first_run.useSelectedDirectory())
                self.assertEqual(config.load_config()["watch_folder"], str(second_path))


class WindowStateTests(unittest.TestCase):
    def test_first_launch_centers_in_available_geometry(self):
        screen = QRect(0, 0, 1920, 1040)
        geometry, fallback = resolve_window_geometry(
            {"x": None, "y": None, "width": 1536, "height": 982},
            [screen],
            screen,
            minimum_width=1080,
            minimum_height=680,
        )
        self.assertTrue(fallback)
        self.assertEqual(geometry, QRect(192, 29, 1536, 982))

    def test_valid_second_monitor_geometry_is_restored(self):
        primary = QRect(0, 0, 1920, 1040)
        second = QRect(1920, 0, 2560, 1400)
        geometry, fallback = resolve_window_geometry(
            {"x": 2200, "y": 120, "width": 1500, "height": 920},
            [primary, second],
            primary,
            minimum_width=1080,
            minimum_height=680,
        )
        self.assertFalse(fallback)
        self.assertEqual(geometry, QRect(2200, 120, 1500, 920))

    def test_removed_monitor_falls_back_and_large_geometry_is_clamped(self):
        primary = QRect(0, 0, 1920, 1040)
        geometry, fallback = resolve_window_geometry(
            {"x": 5000, "y": 5000, "width": 3000, "height": 2000},
            [primary],
            primary,
            minimum_width=1080,
            minimum_height=680,
        )
        self.assertTrue(fallback)
        self.assertEqual(geometry, primary)

    def test_serialization_keeps_normal_geometry_and_maximized_separate(self):
        state = serialize_window_state(QRect(280, 120, 1500, 920), True)
        self.assertEqual(
            state,
            {
                "x": 280,
                "y": 120,
                "width": 1500,
                "height": 920,
                "maximized": True,
            },
        )


if __name__ == "__main__":
    unittest.main()

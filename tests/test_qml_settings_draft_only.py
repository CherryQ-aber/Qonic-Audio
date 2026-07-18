import unittest
from unittest.mock import patch

from ui_next.bridge.settings_viewmodel import SettingsViewModel


class SettingsViewModelDraftOnlyTests(unittest.TestCase):
    def setUp(self):
        self.real_config = {
            "watch_folder": "D:/Music/Incoming",
            "output_folder": "D:/Music/Output",
            "editor_output_folder": "D:/Music/Editor",
            "target_format": "mp3",
            "auto_start_monitor": True,
            "scan_existing_on_start": False,
            "create_format_subfolder": True,
            "embed_lyrics_after_convert": True,
            "copy_lrc_to_output": False,
            "overwrite_existing_lyrics": False,
            "theme_mode": "system",
            "log_level": "INFO",
            "ui_density": "standard",
        }

    def test_preview_changes_and_save_attempt_never_call_save_config(self):
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(self.real_config),
            ),
            patch("ui_next.bridge.settings_viewmodel.save_config") as mock_save,
        ):
            view_model = SettingsViewModel()
            view_model.updatePendingValue("embed_lyrics_after_convert", False)
            view_model.updatePendingValue("copy_lrc_to_output", True)
            view_model.updatePendingValue("overwrite_existing_lyrics", True)
            view_model.updatePendingValue("theme_mode", "dark")
            view_model.updatePendingValue("ui_density", "compact")
            view_model.simulateSaveDraft()
            view_model.savePendingChanges()

        self.assertTrue(view_model.previewMode)
        self.assertTrue(view_model.isDraftOnly)
        self.assertTrue(view_model.isDisabledInPreview)
        self.assertFalse(view_model.canPersistConfig)
        self.assertTrue(view_model.hasPendingChanges)
        self.assertIn("当前不可用", view_model.statusMessage)
        mock_save.assert_not_called()

    def test_discard_restores_real_config_and_clears_pending_state(self):
        with patch(
            "ui_next.bridge.settings_viewmodel.load_config",
            return_value=dict(self.real_config),
        ):
            view_model = SettingsViewModel()
            view_model.updatePendingValue("target_format", "flac")
            view_model.updatePendingValue("auto_start_monitor", False)
            view_model.discardPendingChanges()

        self.assertFalse(view_model.hasPendingChanges)
        self.assertEqual(view_model.pendingConfig, view_model.currentConfig)
        self.assertEqual(view_model.targetFormat, self.real_config["target_format"])
        self.assertEqual(
            view_model.autoStartMonitor,
            self.real_config["auto_start_monitor"],
        )
        self.assertIn("config.json 未改变", view_model.statusMessage)

    def test_reload_replaces_pending_draft_with_latest_real_config(self):
        reloaded_config = dict(self.real_config)
        reloaded_config["target_format"] = "flac"
        with patch(
            "ui_next.bridge.settings_viewmodel.load_config",
            side_effect=[dict(self.real_config), reloaded_config],
        ):
            view_model = SettingsViewModel()
            view_model.updatePendingValue("target_format", "wav")
            view_model.reloadConfig()

        self.assertFalse(view_model.hasPendingChanges)
        self.assertEqual(view_model.targetFormat, "flac")
        self.assertEqual(view_model.pendingConfig, view_model.currentConfig)
        self.assertIn("重新读取真实配置", view_model.statusMessage)

    def test_legacy_live_mode_no_longer_unlocks_config_save(self):
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(self.real_config),
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.save_config",
                return_value=dict(self.real_config),
            ) as mock_save,
            patch.object(SettingsViewModel, "_confirm_live_save") as confirm,
        ):
            view_model = SettingsViewModel(live_mode=True)
            view_model.updatePendingValue("target_format", "flac")
            view_model.savePendingChanges()

        mock_save.assert_not_called()
        confirm.assert_not_called()
        self.assertTrue(view_model.hasPendingChanges)
        self.assertTrue(view_model.previewMode)
        self.assertIn("当前不可用", view_model.statusMessage)


if __name__ == "__main__":
    unittest.main()

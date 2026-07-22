import unittest
from unittest.mock import patch

from config import DEFAULT_CONFIG, _merge_with_default
from ui_next.bridge.capabilities import CapabilityGate
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
            "editor_file_bar_mode": "fixed",
            "lyrics_timestamp_precision": "millisecond",
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
            view_model.setEditorFileBarMode("floating")
            view_model.setLyricsTimestampPrecision("centisecond")
            view_model.simulateSaveDraft()
            view_model.savePendingChanges()

        self.assertTrue(view_model.previewMode)
        self.assertTrue(view_model.isDraftOnly)
        self.assertTrue(view_model.isDisabledInPreview)
        self.assertFalse(view_model.canPersistConfig)
        self.assertTrue(view_model.hasPendingChanges)
        self.assertEqual(view_model.editorFileBarMode, "floating")
        self.assertEqual(view_model.lyricsTimestampPrecision, "centisecond")
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
            view_model.setEditorFileBarMode("floating")
            view_model.setLyricsTimestampPrecision("centisecond")
            view_model.discardPendingChanges()

        self.assertFalse(view_model.hasPendingChanges)
        self.assertEqual(view_model.pendingConfig, view_model.currentConfig)
        self.assertEqual(view_model.targetFormat, self.real_config["target_format"])
        self.assertEqual(
            view_model.autoStartMonitor,
            self.real_config["auto_start_monitor"],
        )
        self.assertEqual(view_model.editorFileBarMode, "fixed")
        self.assertEqual(view_model.lyricsTimestampPrecision, "millisecond")
        self.assertIn("放弃修改", view_model.statusMessage)

    def test_file_bar_mode_rejects_unknown_values(self):
        with patch(
            "ui_next.bridge.settings_viewmodel.load_config",
            return_value=dict(self.real_config),
        ):
            view_model = SettingsViewModel()
            view_model.setEditorFileBarMode("unknown")

        self.assertEqual(view_model.editorFileBarMode, "fixed")
        self.assertFalse(view_model.hasPendingChanges)

    def test_timestamp_precision_defaults_to_milliseconds_and_rejects_unknown(self):
        self.assertEqual(
            "millisecond",
            DEFAULT_CONFIG["lyrics_timestamp_precision"],
        )
        self.assertEqual(
            "millisecond",
            _merge_with_default({})["lyrics_timestamp_precision"],
        )
        self.assertEqual(
            "millisecond",
            _merge_with_default(
                {"lyrics_timestamp_precision": "unknown"}
            )["lyrics_timestamp_precision"],
        )
        self.assertEqual(
            "centisecond",
            _merge_with_default(
                {"lyrics_timestamp_precision": "centisecond"}
            )["lyrics_timestamp_precision"],
        )

        with patch(
            "ui_next.bridge.settings_viewmodel.load_config",
            return_value=dict(self.real_config),
        ):
            view_model = SettingsViewModel()
            view_model.setLyricsTimestampPrecision("unknown")

        self.assertEqual(view_model.lyricsTimestampPrecision, "millisecond")
        self.assertFalse(view_model.hasPendingChanges)

    def test_timestamp_precision_is_in_confirmed_config_whitelist(self):
        gate = CapabilityGate.from_environment(
            {"CHERRYQ_QML_USER_TEST": "1"}
        )
        saved_config = {}

        def save_config(config_data):
            saved_config.update(config_data)
            return dict(config_data)

        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(self.real_config),
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.save_config",
                side_effect=save_config,
            ),
            patch.object(
                SettingsViewModel,
                "_confirm_live_save",
                return_value=True,
            ),
        ):
            view_model = SettingsViewModel(capability_gate=gate)
            view_model.setLyricsTimestampPrecision("centisecond")
            view_model.savePendingChanges()

        self.assertEqual(
            "centisecond",
            saved_config["lyrics_timestamp_precision"],
        )

    def test_save_merges_only_confirmed_changes_onto_latest_config(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})
        latest_config = dict(self.real_config)
        latest_config["theme_mode"] = "dark"
        saved_config = {}

        def save_config(config_data):
            saved_config.update(config_data)
            return dict(config_data)

        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                side_effect=[dict(self.real_config), latest_config],
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.save_config",
                side_effect=save_config,
            ),
            patch.object(SettingsViewModel, "_confirm_live_save", return_value=True),
        ):
            view_model = SettingsViewModel(capability_gate=gate)
            view_model.setTargetFormat("flac")
            view_model.savePendingChanges()

        self.assertEqual("flac", saved_config["target_format"])
        self.assertEqual("dark", saved_config["theme_mode"])

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
        self.assertIn("重新载入设置", view_model.statusMessage)

    def test_pending_change_list_contains_only_modified_settings(self):
        with patch(
            "ui_next.bridge.settings_viewmodel.load_config",
            return_value=dict(self.real_config),
        ):
            view_model = SettingsViewModel()
            view_model.updatePendingValue("target_format", "flac")
            view_model.updatePendingValue("theme_mode", "dark")

        self.assertEqual(2, view_model.pendingChangeCount)
        self.assertEqual(
            ["target_format", "theme_mode"],
            [item["key"] for item in view_model.pendingChangeItems],
        )
        self.assertTrue(view_model.pendingChangeItems[0]["automaticConversion"])
        self.assertFalse(view_model.pendingChangeItems[1]["automaticConversion"])
        self.assertIn("目标格式：MP3 → FLAC", view_model.pendingChangeSummary)
        self.assertNotIn("监听目录", view_model.pendingChangeSummary)

    def test_running_conversion_blocks_auto_convert_setting_save(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})

        class BusyAutoConvert:
            isConverting = True
            hasBackgroundTask = True

        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(self.real_config),
            ),
            patch("ui_next.bridge.settings_viewmodel.save_config") as mock_save,
            patch.object(SettingsViewModel, "_confirm_live_save") as confirm,
        ):
            view_model = SettingsViewModel(capability_gate=gate)
            view_model._auto_convert_view_model = BusyAutoConvert()
            view_model.updatePendingValue("target_format", "flac")
            view_model.savePendingChanges()

        self.assertTrue(view_model.autoConvertBusy)
        self.assertFalse(view_model.canApplyPendingChanges)
        self.assertIn("自动转码正在运行", view_model.statusMessage)
        confirm.assert_not_called()
        mock_save.assert_not_called()

    def test_confirm_dialog_lists_current_changes(self):
        from PySide6.QtWidgets import QMessageBox

        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=dict(self.real_config),
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as question,
        ):
            view_model = SettingsViewModel(capability_gate=gate)
            view_model.updatePendingValue("target_format", "flac")
            view_model._confirm_live_save()

        message = question.call_args.args[2]
        self.assertIn("目标格式：MP3 → FLAC", message)
        self.assertIn("自动转码相关设置将在确认后生效", message)
        self.assertNotIn("监听目录", message)

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

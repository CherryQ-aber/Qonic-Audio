import unittest
from unittest.mock import MagicMock, patch

from ui_next.bridge.auto_convert_viewmodel import AutoConvertViewModel
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    AUDIO_EXPORT,
    AUDIO_PLAYBACK,
    AUDIO_PROCESSING,
    CONFIG_WRITE,
    COVER_READ,
    COVER_WRITE,
    LYRICS_READ,
    LYRICS_WRITE,
    METADATA_READ,
    METADATA_WRITE,
    OVERWRITE_FILE,
    QUEUE_MUTATION,
    SCAN_PREVIEW,
    SINGLE_FILE_CONVERT,
    WATCHER_CONTROL,
    DEFAULT_USER_CAPABILITIES,
    CapabilityGate,
)
from ui_next.bridge.settings_viewmodel import SettingsViewModel


class CapabilityGateTests(unittest.TestCase):
    def test_default_environment_uses_the_default_user_profile(self):
        gate = CapabilityGate.from_environment({})

        self.assertFalse(gate.previewMode)
        self.assertTrue(gate.liveMode)
        self.assertEqual(set(gate.enabledCapabilities), DEFAULT_USER_CAPABILITIES)

    def test_completed_read_capabilities_are_independent(self):
        gate = CapabilityGate.from_environment(
            {
                "CHERRYQ_QML_CAPS": (
                    "metadata_read,lyrics_read,cover_read"
                )
            }
        )

        self.assertFalse(gate.previewMode)
        self.assertEqual(
            gate.enabledCapabilities,
            [METADATA_READ, LYRICS_READ, COVER_READ],
        )
        self.assertTrue(gate.allows(METADATA_READ))
        self.assertTrue(gate.allows(LYRICS_READ))
        self.assertTrue(gate.allows(COVER_READ))
        self.assertFalse(gate.allows(CONFIG_WRITE))
        self.assertFalse(gate.allows(WATCHER_CONTROL))

    def test_explicit_capabilities_are_independent(self):
        gate = CapabilityGate.from_environment(
            {
                "CHERRYQ_QML_CAPS": (
                    "cover_read,cover_write,metadata_write,"
                    "watcher_control,config_write"
                )
            }
        )

        self.assertEqual(
            gate.enabledCapabilities,
            [COVER_READ, CONFIG_WRITE, WATCHER_CONTROL, METADATA_WRITE, COVER_WRITE],
        )
        self.assertTrue(gate.allows(COVER_READ))
        self.assertTrue(gate.allows(COVER_WRITE))
        self.assertTrue(gate.allows(METADATA_WRITE))
        self.assertTrue(gate.allows(WATCHER_CONTROL))
        self.assertTrue(gate.allows(CONFIG_WRITE))
        self.assertFalse(gate.allows(QUEUE_MUTATION))
        self.assertFalse(gate.allows(BATCH_CONVERT))

    def test_scan_preview_can_be_combined_with_explicit_workflow_actions(self):
        gate = CapabilityGate.from_environment(
            {
                "CHERRYQ_QML_CAPS": (
                    "scan_preview,watcher_control,queue_mutation,"
                    "batch_convert,config_write"
                )
            }
        )

        self.assertEqual(
            gate.enabledCapabilities,
            [SCAN_PREVIEW, CONFIG_WRITE, WATCHER_CONTROL, QUEUE_MUTATION, BATCH_CONVERT],
        )
        self.assertTrue(gate.allows(SCAN_PREVIEW))
        self.assertTrue(gate.allows(WATCHER_CONTROL))
        self.assertTrue(gate.allows(QUEUE_MUTATION))
        self.assertTrue(gate.allows(BATCH_CONVERT))
        self.assertTrue(gate.allows(CONFIG_WRITE))
        self.assertFalse(gate.allows(OVERWRITE_FILE))

    def test_single_file_convert_can_be_combined_with_workflow_without_overwrite(self):
        gate = CapabilityGate.from_environment(
            {
                "CHERRYQ_QML_CAPS": (
                    "single_file_convert,watcher_control,queue_mutation,"
                    "batch_convert,config_write,overwrite_file,"
                    "metadata_write,lyrics_write,cover_write"
                )
            }
        )

        self.assertEqual(
            gate.enabledCapabilities,
            [
                SINGLE_FILE_CONVERT,
                CONFIG_WRITE,
                WATCHER_CONTROL,
                QUEUE_MUTATION,
                BATCH_CONVERT,
                LYRICS_WRITE,
                METADATA_WRITE,
                COVER_WRITE,
            ],
        )
        self.assertTrue(gate.allows(SINGLE_FILE_CONVERT))
        self.assertTrue(gate.allows(WATCHER_CONTROL))
        self.assertTrue(gate.allows(QUEUE_MUTATION))
        self.assertTrue(gate.allows(BATCH_CONVERT))
        self.assertTrue(gate.allows(CONFIG_WRITE))
        self.assertIn(OVERWRITE_FILE, gate.deniedCapabilities)

    def test_legacy_live_flag_does_not_change_the_default_user_profile(self):
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_LIVE": "1"})

        self.assertTrue(gate.legacyLiveRequested)
        self.assertFalse(gate.previewMode)
        self.assertEqual(set(gate.enabledCapabilities), DEFAULT_USER_CAPABILITIES)
        self.assertFalse(gate.allows(OVERWRITE_FILE))

    def test_legacy_user_trial_environment_remains_a_fixed_compatibility_profile(self):
        gate = CapabilityGate.from_environment(
            {
                "CHERRYQ_QML_USER_TEST": "1",
                # The trial profile must not be widened by a stale shell env.
                "CHERRYQ_QML_CAPS": "overwrite_file,metadata_write",
            }
        )

        self.assertTrue(gate.userTrialMode)
        self.assertFalse(gate.previewMode)
        self.assertEqual(gate.modeLabel, "Default User Mode")
        self.assertEqual(gate.userModeLabel, "正常运行")
        self.assertEqual(set(gate.enabledCapabilities), DEFAULT_USER_CAPABILITIES)
        self.assertTrue(gate.allows(SCAN_PREVIEW))
        self.assertTrue(gate.allows(SINGLE_FILE_CONVERT))
        self.assertTrue(gate.allows(BATCH_CONVERT))
        self.assertTrue(gate.allows(QUEUE_MUTATION))
        self.assertTrue(gate.allows(WATCHER_CONTROL))
        self.assertTrue(gate.allows(CONFIG_WRITE))
        self.assertTrue(gate.allows(AUDIO_PLAYBACK))
        self.assertTrue(gate.allows(AUDIO_PROCESSING))
        self.assertTrue(gate.allows(AUDIO_EXPORT))
        self.assertTrue(gate.allows(METADATA_WRITE))
        self.assertTrue(gate.allows(LYRICS_WRITE))
        self.assertTrue(gate.allows(COVER_WRITE))
        self.assertFalse(gate.allows(OVERWRITE_FILE))
        self.assertTrue(gate.sourceFileProtectionEnabled)
        self.assertIn("扫描", gate.enabledFeatureSummary)
        self.assertIn("音频处理", gate.enabledFeatureSummary)

    def test_user_trial_config_write_still_needs_explicit_save_and_confirmation(self):
        current_config = {
            "watch_folder": "D:/Music/Incoming",
            "output_folder": "D:/Music/Output",
            "editor_output_folder": "D:/Music/Editor",
            "target_format": "mp3",
        }
        gate = CapabilityGate.from_environment({"CHERRYQ_QML_USER_TEST": "1"})
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=current_config,
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.save_config",
                side_effect=lambda data: dict(data),
            ) as save_config,
        ):
            view_model = SettingsViewModel(capability_gate=gate)
            view_model.updatePendingValue("target_format", "flac")

            with patch.object(view_model, "_confirm_live_save", return_value=False):
                view_model.savePendingChanges()
            save_config.assert_not_called()

            with patch.object(view_model, "_confirm_live_save", return_value=True):
                view_model.savePendingChanges()
            save_config.assert_called_once()

    def test_workflow_capabilities_are_allowed_but_unknown_is_rejected(self):
        gate = CapabilityGate(
            "config_write,watcher_control,queue_mutation,batch_convert,unknown"
        )

        self.assertEqual(
            gate.enabledCapabilities,
            [CONFIG_WRITE, WATCHER_CONTROL, QUEUE_MUTATION, BATCH_CONVERT],
        )
        self.assertEqual(
            gate.deniedCapabilities,
            ["unknown"],
        )

    def test_single_file_convert_is_independent_from_wider_workflow(self):
        gate = CapabilityGate(SINGLE_FILE_CONVERT)

        self.assertTrue(gate.allows(SINGLE_FILE_CONVERT))
        self.assertFalse(gate.allows(WATCHER_CONTROL))
        self.assertFalse(gate.allows(QUEUE_MUTATION))
        self.assertFalse(gate.allows(CONFIG_WRITE))
        self.assertFalse(gate.allows(BATCH_CONVERT))


class CapabilityGuardIntegrationTests(unittest.TestCase):
    def test_metadata_capability_does_not_unlock_auto_convert(self):
        gate = CapabilityGate(METADATA_READ)
        queue_model = MagicMock()
        queue_model.lastRefreshTime = "12:34:56"

        with (
            patch(
                "ui_next.bridge.auto_convert_viewmodel.watcher.start_watch"
            ) as start_watch,
            patch(
                "ui_next.bridge.auto_convert_viewmodel.watcher.scan_existing_files"
            ) as scan,
            patch(
                "ui_next.bridge.auto_convert_viewmodel.watcher.get_convertible_tasks"
            ) as convert,
            patch(
                "ui_next.bridge.auto_convert_viewmodel.save_config"
            ) as save_config,
        ):
            view_model = AutoConvertViewModel(
                queue_model,
                capability_gate=gate,
            )
            view_model.start_monitor()
            self.assertIn("当前不可用", view_model.statusMessage)
            view_model.scan_existing_files()
            self.assertIn("当前不可用", view_model.statusMessage)
            view_model.start_convert()
            self.assertIn("当前不可用", view_model.statusMessage)
            view_model.set_global_target_format("flac")
            self.assertIn("设置", view_model.statusMessage)

        start_watch.assert_not_called()
        scan.assert_not_called()
        convert.assert_not_called()
        save_config.assert_not_called()
        view_model.shutdown()

    def test_legacy_live_parameter_does_not_unlock_config_write(self):
        real_config = {
            "watch_folder": "D:/Music/Incoming",
            "output_folder": "D:/Music/Output",
            "editor_output_folder": "D:/Music/Editor",
            "target_format": "mp3",
        }
        with (
            patch(
                "ui_next.bridge.settings_viewmodel.load_config",
                return_value=real_config,
            ),
            patch(
                "ui_next.bridge.settings_viewmodel.save_config"
            ) as save_config,
        ):
            view_model = SettingsViewModel(live_mode=True)
            view_model.updatePendingValue("target_format", "flac")
            view_model.savePendingChanges()

        save_config.assert_not_called()
        self.assertTrue(view_model.previewMode)
        self.assertIn("当前不可用", view_model.statusMessage)


if __name__ == "__main__":
    unittest.main()

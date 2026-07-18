import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase595GlobalPlayerDockContractTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_app_shell_owns_the_only_production_player_view(self):
        shell = self._source("ui_next/qml/AppShell.qml")
        editor = self._source(
            "ui_next/qml/components/AudioEditorWorkspace.qml"
        )
        compatibility = self._source(
            "ui_next/qml/components/PlayerBar.qml"
        )

        self.assertEqual(1, shell.count("GlobalPlayerDock {"))
        self.assertIn("audioPlayer: audioPlayerViewModel", shell)
        self.assertIn("compactMode: root.height < 800", shell)
        self.assertIn("narrowMode: root.width < 1320", shell)
        self.assertNotIn("BottomStatusBar {", shell)
        self.assertNotIn("PlayerBar {", editor)
        self.assertNotIn("audioEditorPlayerCard", editor)
        self.assertIn("GlobalPlayerDock {", compatibility)
        self.assertIn("Compatibility surface retained", compatibility)

    def test_dock_has_standard_compact_layout_and_named_responsibilities(self):
        dock = self._source(
            "ui_next/qml/components/GlobalPlayerDock.qml"
        )
        self.assertIn(
            "readonly property int requestedHeight: compactMode ? 82 : 96",
            dock,
        )
        for component_name in (
            "PlayerMediaInfo",
            "PlayerControls",
            "PlayerTimeline",
            "SeekStepControls",
            "PlaybackDeviceControl",
            "TimestampTools",
        ):
            self.assertEqual(
                1,
                dock.count(component_name + " {"),
                component_name,
            )

    def test_controls_follow_player_session_not_editor_session(self):
        controls = self._source(
            "ui_next/qml/components/PlayerControls.qml"
        )
        timeline = self._source(
            "ui_next/qml/components/PlayerTimeline.qml"
        )
        seek = self._source(
            "ui_next/qml/components/SeekStepControls.qml"
        )
        timestamp = self._source(
            "ui_next/qml/components/TimestampTools.qml"
        )

        self.assertIn("root.audioPlayer.canPlay", controls)
        self.assertIn("root.audioPlayer.hasPlaybackSource", controls)
        self.assertNotIn("hasCurrentFile", controls + timeline + seek)
        self.assertIn("root.audioPlayer.hasPlaybackSource", timeline)
        self.assertIn("root.audioPlayer.seekBackward()", seek)
        self.assertIn("root.audioPlayer.seekForward()", seek)
        self.assertIn("后退 \" + root.stepSeconds + \" 秒", seek)
        self.assertIn("前进 \" + root.stepSeconds + \" 秒", seek)
        self.assertIn("copyCurrentTimestamp()", timestamp)

    def test_origin_labels_and_device_switching_contract_are_explicit(self):
        media = self._source(
            "ui_next/qml/components/PlayerMediaInfo.qml"
        )
        device = self._source(
            "ui_next/qml/components/PlaybackDeviceControl.qml"
        )
        for key, label in (
            ("folder_tree", "文件夹树载入"),
            ("transcode_source", "转码源文件"),
            ("transcode_output", "转码输出结果"),
            ("editor_file", "编辑文件"),
            ("pitch_preview", "Pitch 试听"),
            ("editor_export", "编辑导出结果"),
        ):
            self.assertIn(f'origin === "{key}"', media)
            self.assertIn(f'return "{label}"', media)
        self.assertIn("playbackMatchesEditorFile", media)
        self.assertIn("root.audioPlayer.error", media)
        self.assertIn("onDownChanged", device)
        self.assertIn("refreshOutputDevices()", device)
        self.assertIn("onActivated", device)
        self.assertIn("selectOutputDevice", device)

    def test_qml_player_surface_does_not_create_a_second_backend(self):
        qml_paths = (
            "ui_next/qml/AppShell.qml",
            "ui_next/qml/components/GlobalPlayerDock.qml",
            "ui_next/qml/components/PlayerBar.qml",
            "ui_next/qml/components/PlayerControls.qml",
            "ui_next/qml/components/PlayerTimeline.qml",
            "ui_next/qml/components/PlaybackDeviceControl.qml",
        )
        combined = "\n".join(self._source(path) for path in qml_paths)
        self.assertNotIn("QMediaPlayer", combined)
        self.assertNotIn("QAudioOutput", combined)


if __name__ == "__main__":
    unittest.main()

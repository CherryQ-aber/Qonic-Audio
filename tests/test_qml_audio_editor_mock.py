import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui_next.bridge.editor_session_viewmodel import EditorSessionViewModel


class EditorSessionMockFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _import_mock_path(self, view_model, audio_path):
        with patch(
            "ui_next.bridge.editor_session_viewmodel.QFileDialog.getOpenFileName",
            return_value=(str(audio_path), "音频文件"),
        ):
            view_model.importAudioMock()

    def test_import_only_records_path_and_player_states_are_mock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "sample.mp3"
            original_bytes = b"not-real-audio-content"
            audio_path.write_bytes(original_bytes)
            before_names = sorted(path.name for path in Path(temp_dir).iterdir())

            view_model = EditorSessionViewModel()
            with patch("builtins.open") as mock_open:
                self._import_mock_path(view_model, audio_path)
            mock_open.assert_not_called()

            self.assertTrue(view_model.previewMode)
            self.assertTrue(view_model.isMockSession)
            self.assertTrue(view_model.hasCurrentFile)
            self.assertEqual(view_model.currentFilePath, str(audio_path))
            self.assertEqual(view_model.duration, 260000)

            view_model.playMock()
            self.assertEqual(view_model.playerState, "playing")
            view_model.seekMock(12000)
            self.assertEqual(view_model.position, 12000)
            view_model.pauseMock()
            self.assertEqual(view_model.playerState, "paused")
            view_model.setVolume(35)
            self.assertEqual(view_model.volume, 35)
            view_model.stopMock()
            self.assertEqual(view_model.playerState, "stopped")
            self.assertEqual(view_model.position, 0)

            self.assertEqual(audio_path.read_bytes(), original_bytes)
            self.assertEqual(
                sorted(path.name for path in Path(temp_dir).iterdir()),
                before_names,
            )
            view_model._play_timer.stop()

    def test_preview_and_export_use_transient_states_without_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_path = root / "sample.flac"
            audio_path.write_bytes(b"placeholder")
            before = {path.name: path.read_bytes() for path in root.iterdir()}

            view_model = EditorSessionViewModel()
            self._import_mock_path(view_model, audio_path)
            view_model.setPitchSemitone(3)
            self.assertEqual(view_model.previewState, "未生成模拟试听")
            self.assertEqual(view_model.exportState, "未模拟导出")
            view_model.previewPitchMock()

            self.assertTrue(view_model.isPreviewGenerating)
            self.assertEqual(view_model.previewState, "正在生成模拟试听")
            QTest.qWait(380)
            self.assertFalse(view_model.isPreviewGenerating)
            self.assertEqual(view_model.previewState, "已生成模拟试听")
            self.assertTrue(view_model.currentPlaySource.startswith("preview://"))
            self.assertIn("+3", view_model.previewVersionLabel)

            view_model.exportPitchMock()
            self.assertTrue(view_model.isExporting)
            self.assertEqual(view_model.exportState, "正在模拟导出")
            QTest.qWait(380)
            self.assertFalse(view_model.isExporting)
            self.assertEqual(view_model.exportState, "模拟导出完成")
            self.assertEqual(view_model.lastExportPath, "<mock>/sample_pitch+3.flac")

            self.assertEqual(
                {path.name: path.read_bytes() for path in root.iterdir()},
                before,
            )

    def test_loading_mock_export_only_changes_session_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "source.wav"
            audio_path.write_bytes(b"placeholder")

            view_model = EditorSessionViewModel()
            self._import_mock_path(view_model, audio_path)
            view_model.setPitchSemitone(-2)
            view_model.exportPitchMock()
            QTest.qWait(380)
            mock_path = view_model.lastExportPath

            view_model.loadExportResultAsCurrentMock()
            self.assertTrue(view_model.currentFileIsMockExport)
            self.assertEqual(view_model.currentFilePath, mock_path)
            self.assertFalse(Path(mock_path).exists())

            view_model.returnToOriginalMock()
            self.assertEqual(view_model.currentPlaySource, str(audio_path))
            self.assertEqual(view_model.currentFilePath, mock_path)
            self.assertIn("没有播放真实音频", view_model.statusMessage)

    def test_pitch_limits_and_clear_reset_all_mock_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "source.ogg"
            audio_path.write_bytes(b"placeholder")

            view_model = EditorSessionViewModel()
            self._import_mock_path(view_model, audio_path)
            view_model.setPitchSemitone(99)
            self.assertEqual(view_model.pitchSemitone, 12)
            view_model.setPitchSemitone(-99)
            self.assertEqual(view_model.pitchSemitone, -12)
            view_model.clearCurrentAudio()

            self.assertFalse(view_model.hasCurrentFile)
            self.assertEqual(view_model.playerState, "stopped")
            self.assertEqual(view_model.pitchSemitone, 0)
            self.assertEqual(view_model.previewState, "未生成模拟试听")
            self.assertEqual(view_model.exportState, "未模拟导出")
            self.assertFalse(view_model.hasLastExport)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReadonlyWorkflowWiringTests(unittest.TestCase):
    def _source(self, path):
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_main_uses_file_session_instead_of_editor_state_changed_reads(self):
        source = self._source("main_qml.py")
        self.assertIn("FileSessionViewModel", source)
        self.assertIn("file_session_view_model.attach_readers", source)
        self.assertNotIn("editor_session.stateChanged.connect(sync_editor_session_file)", source)

    def test_qml_entry_points_route_to_the_shared_session(self):
        metadata = self._source("ui_next/qml/pages/MetadataPage.qml")
        lyrics = self._source("ui_next/qml/pages/LyricsCoverPage.qml")
        scan = self._source("ui_next/qml/components/ScanPreviewPanel.qml")
        single = self._source("ui_next/qml/components/SingleFileConvertPanel.qml")
        inspector = self._source("ui_next/qml/components/RightInspector.qml")
        self.assertIn('chooseAudioFile("metadata_page")', metadata)
        self.assertIn('chooseAudioFile("lyrics_cover_page")', lyrics)
        self.assertIn("loadSelectedFileIntoWorkspace", scan)
        self.assertIn("setInputFileFromCurrentSession", single)
        self.assertIn("currentFileSourceLabel", inspector)

    def test_workflow_keeps_single_convert_and_queue_boundaries(self):
        scan = self._source("ui_next/bridge/scan_preview_viewmodel.py")
        single = self._source("ui_next/bridge/single_file_convert_viewmodel.py")
        session = self._source("ui_next/bridge/file_session_viewmodel.py")
        self.assertIn("requestCurrentFileSession", scan)
        self.assertIn("setInputFileFromCurrentSession", single)
        self.assertIn("_output_path = \"\"", single)
        self.assertNotIn("import watcher", session)
        self.assertNotIn("save_config", session)


if __name__ == "__main__":
    unittest.main()

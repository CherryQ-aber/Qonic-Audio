import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import scan_preview
from ui_next.bridge.capabilities import (
    SCAN_PREVIEW,
    SINGLE_FILE_CONVERT,
    CapabilityGate,
)
from ui_next.bridge.scan_preview_viewmodel import ScanPreviewViewModel
from ui_next.bridge.single_file_convert_viewmodel import SingleFileConvertViewModel


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ScanPreviewServiceTests(unittest.TestCase):
    def test_scan_directory_preview_is_extension_only_and_readonly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                "song.flac": b"audio-placeholder",
                "song.lrc": b"[00:01.00]lyric\n",
                "demo.mp3": b"mp3-placeholder",
                "notes.txt": b"notes",
                "cover.jpg": b"jpeg",
            }
            for name, content in files.items():
                (root / name).write_bytes(content)
            (root / "nested").mkdir()
            (root / "nested" / "hidden.opus").write_bytes(b"nested-opus")
            before_hashes = {
                path.relative_to(root).as_posix(): file_sha(path)
                for path in root.rglob("*")
                if path.is_file()
            }

            result = scan_preview.scan_directory_preview(str(root))

            after_hashes = {
                path.relative_to(root).as_posix(): file_sha(path)
                for path in root.rglob("*")
                if path.is_file()
            }

        self.assertTrue(result["ok"])
        self.assertFalse(result["recursive"])
        self.assertEqual(result["supported_count"], 2)
        self.assertEqual(result["lrc_count"], 1)
        self.assertEqual(result["unsupported_count"], 2)
        self.assertEqual(before_hashes, after_hashes)

        items_by_name = {item["filename"]: item for item in result["items"]}
        self.assertTrue(items_by_name["song.flac"]["is_supported_audio"])
        self.assertTrue(items_by_name["song.flac"]["has_matching_lrc"])
        self.assertTrue(items_by_name["song.flac"]["matching_lrc_path"].lower().endswith(".lrc"))
        self.assertEqual(
            items_by_name["song.lrc"]["skip_reason"],
            "歌词文件，仅作为匹配候选",
        )
        self.assertEqual(
            items_by_name["notes.txt"]["skip_reason"],
            "不支持的扩展名",
        )
        self.assertEqual(
            items_by_name["nested"]["skip_reason"],
            "目录项，当前未递归扫描",
        )
        self.assertNotIn("hidden.opus", items_by_name)

    def test_recursive_scan_is_explicit_and_limited(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.mp3").write_bytes(b"a")
            nested = root / "nested"
            nested.mkdir()
            (nested / "b.opus").write_bytes(b"b")

            result = scan_preview.scan_directory_preview(
                str(root),
                recursive=True,
            )

        names = {item["filename"] for item in result["items"]}
        self.assertTrue(result["ok"])
        self.assertTrue(result["recursive"])
        self.assertIn("a.mp3", names)
        self.assertIn("b.opus", names)

    def test_scan_limit_truncates_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for index in range(5):
                (root / f"{index}.flac").write_bytes(str(index).encode("utf-8"))

            result = scan_preview.scan_directory_preview(
                str(root),
                max_files=2,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["too_many_files"])
        self.assertEqual(len(result["items"]), 2)
        self.assertIn("上限 2", result["error"])


class ScanPreviewViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_scan(self, view_model: ScanPreviewViewModel) -> None:
        if not view_model.isScanning:
            return
        loop = QEventLoop()

        def maybe_quit():
            if not view_model.isScanning:
                loop.quit()

        view_model.stateChanged.connect(maybe_quit)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        try:
            view_model.stateChanged.disconnect(maybe_quit)
        except (RuntimeError, TypeError):
            pass
        self.assertFalse(view_model.isScanning)

    def test_preview_mode_records_folder_without_scanning(self):
        view_model = ScanPreviewViewModel()

        with patch(
            "ui_next.bridge.scan_preview_viewmodel.scan_directory_preview"
        ) as scanner:
            view_model.scanFolderPreview("D:/Music")

        scanner.assert_not_called()
        self.assertTrue(view_model.previewMode)
        self.assertEqual(view_model.folderPath, "D:/Music")
        self.assertEqual(view_model.itemCount, 0)
        self.assertIn("目录扫描不可用", view_model.statusMessage)

    def test_enabled_scan_maps_result_from_worker_thread(self):
        fake_result = {
            "ok": True,
            "folder_path": "D:/Music",
            "recursive": False,
            "total_entries": 2,
            "scanned_files": 2,
            "supported_count": 1,
            "unsupported_count": 0,
            "lrc_count": 1,
            "too_many_files": False,
            "items": [
                {
                    "path": "D:/Music/song.flac",
                    "filename": "song.flac",
                    "extension": "flac",
                    "format_label": "FLAC",
                    "size_text": "12 B",
                    "size_bytes": 12,
                    "is_supported_audio": True,
                    "is_ncm": False,
                    "is_lrc": False,
                    "is_directory": False,
                    "has_matching_lrc": True,
                    "matching_lrc_path": "D:/Music/song.lrc",
                    "skip_reason": "",
                    "source": "scan_preview",
                }
            ],
        }
        view_model = ScanPreviewViewModel(CapabilityGate(SCAN_PREVIEW))
        with patch(
            "ui_next.bridge.scan_preview_viewmodel.scan_directory_preview",
            return_value=fake_result,
        ) as scanner:
            view_model.scanFolderPreview("D:/Music")
            self.wait_for_scan(view_model)

        scanner.assert_called_once_with(
            "D:/Music",
            recursive=False,
            max_files=scan_preview.DEFAULT_MAX_FILES,
            stop_event=ANY,
            progress_callback=ANY,
        )
        self.assertFalse(view_model.previewMode)
        self.assertEqual(view_model.supportedCount, 1)
        self.assertEqual(view_model.lrcCount, 1)
        self.assertEqual(view_model.itemCount, 1)
        self.assertIn("扫描预览完成", view_model.statusMessage)

    def test_disabled_actions_are_noop(self):
        view_model = ScanPreviewViewModel(CapabilityGate(SCAN_PREVIEW))

        view_model.disabledAddToQueue()
        view_model.disabledStartConvert()
        view_model.disabledScanAndQueue()
        view_model.disabledApplyTargetFormat()

        self.assertEqual(
            view_model.statusMessage,
            "此操作当前不可用，未执行任何更改。",
        )

    def test_selected_audio_handoff_sets_single_convert_input_without_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "scan candidate.flac"
            source.write_bytes(b"audio-placeholder")
            gate = CapabilityGate((SCAN_PREVIEW, SINGLE_FILE_CONVERT))
            scan_view_model = ScanPreviewViewModel(gate)
            single_view_model = SingleFileConvertViewModel(gate)
            scan_view_model._items = [
                {
                    "path": str(source),
                    "filename": source.name,
                    "is_supported_audio": True,
                }
            ]
            single_view_model.setOutputPath(str(Path(temp_dir) / "old-output.flac"))
            scan_view_model.requestSingleFileConvert.connect(
                single_view_model.setInputFileFromPreview
            )

            scan_view_model.selectAudioCandidate(str(source))
            scan_view_model.sendSelectedFileToSingleConvert()

            self.assertEqual(scan_view_model.selectedFilePath, str(source))
            self.assertTrue(scan_view_model.canUseSelectedFileForConvert)
            self.assertEqual(single_view_model.inputPath, str(source))
            self.assertEqual(single_view_model.inputSourceLabel, "目录扫描预览")
            self.assertEqual(single_view_model.outputPath, "")
            self.assertEqual(single_view_model.convertStatus, "等待输出路径")
            self.assertEqual(
                single_view_model.statusMessage,
                "文件已载入，请选择新的输出路径后开始转换。",
            )

    def test_scan_only_cannot_handoff_selected_file_to_converter(self):
        view_model = ScanPreviewViewModel(CapabilityGate(SCAN_PREVIEW))
        view_model._items = [
            {
                "path": "D:/Music/song.flac",
                "filename": "song.flac",
                "is_supported_audio": True,
            }
        ]
        requested_paths = []
        view_model.requestSingleFileConvert.connect(requested_paths.append)

        view_model.selectAudioCandidate("D:/Music/song.flac")
        view_model.sendSelectedFileToSingleConvert()

        self.assertTrue(view_model.hasSelectedAudio)
        self.assertFalse(view_model.canUseSelectedFileForConvert)
        self.assertEqual(requested_paths, [])
        self.assertEqual("此操作当前不可用，未执行任何更改。", view_model.statusMessage)

    def test_viewmodel_does_not_import_forbidden_runtime_modules(self):
        source = Path("ui_next/bridge/scan_preview_viewmodel.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("import watcher", source)
        self.assertNotIn("import converter", source)
        self.assertNotIn("save_config", source)


if __name__ == "__main__":
    unittest.main()

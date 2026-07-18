import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AutoConvertResponsiveLayoutTests(unittest.TestCase):
    def _qml_source(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_auto_convert_page_gives_vertical_scroll_ownership_to_the_queue(self):
        page_source = self._qml_source("ui_next/qml/pages/AutoConvertPage.qml")
        queue_source = self._qml_source("ui_next/qml/components/TaskQueueView.qml")

        self.assertNotIn("Flickable {", page_source)
        self.assertNotIn("ScrollBar.vertical", page_source)
        self.assertIn("id: workspaceLayout", page_source)
        self.assertIn("objectName: \"autoConvertPrimaryQueue\"", page_source)
        self.assertIn("Layout.fillHeight: true", page_source)
        self.assertEqual(queue_source.count("ListView {"), 1)
        self.assertIn("id: queueList", queue_source)
        self.assertIn("Layout.fillHeight: true", queue_source)

    def test_auto_convert_page_loads_only_the_unified_queue(self):
        page_source = self._qml_source("ui_next/qml/pages/AutoConvertPage.qml")
        queue_source = self._qml_source("ui_next/qml/components/TaskQueueView.qml")

        self.assertNotIn("ScanPreviewPanel {", page_source)
        self.assertNotIn("SingleFileConvertPanel {", page_source)
        self.assertIn("ScanSummaryBar {", page_source)
        self.assertEqual(page_source.count("TaskQueueView {"), 1)
        self.assertIn("implicitHeight: 260", queue_source)
        self.assertIn("Layout.minimumHeight: 132", queue_source)

    def test_auto_convert_actions_bind_to_capabilities_and_runtime_state(self):
        page_source = self._qml_source("ui_next/qml/pages/AutoConvertPage.qml")
        action_source = self._qml_source(
            "ui_next/qml/components/ConvertActionBar.qml"
        )

        for label in (
            "添加文件",
            "扫描目录",
            "开始监听",
        ):
            self.assertIn(label, page_source)

        for capability in (
            "autoConvertViewModel.canAddFiles",
            "autoConvertViewModel.canScanDirectories",
            "autoConvertViewModel.canControlWatcher",
        ):
            self.assertIn(capability, page_source)

        for call in (
            "autoConvertViewModel.choose_input_files()",
            "autoConvertViewModel.choose_scan_folder()",
            "autoConvertViewModel.start_monitor()",
            "autoConvertViewModel.stop_monitor()",
        ):
            self.assertIn(call, page_source)

        for label in (
            "开始转换",
            "取消当前任务",
            "完成当前后停止",
            "清除终态",
            "重试失败",
        ):
            self.assertIn(f'text: "{label}"', action_source)

        self.assertIn("root.autoConvertViewModel.canBatchConvert", action_source)
        self.assertIn("root.autoConvertViewModel.canMutateQueue", action_source)
        self.assertIn("root.autoConvertViewModel.canCancelCurrentTask", action_source)
        self.assertIn("autoConvertViewModel.start_convert()", action_source)
        self.assertIn("autoConvertViewModel.clear_terminal_items()", action_source)
        self.assertIn("预览模式不会监听、入队、转换、保存设置或修改 config.json。", page_source)


if __name__ == "__main__":
    unittest.main()

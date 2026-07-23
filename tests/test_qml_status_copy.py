import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlStatusCopyTests(unittest.TestCase):
    def _qml_source(self, relative_path: str) -> str:
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    def test_top_bar_omits_runtime_badges_without_exposing_capability_ids(self):
        shell = self._qml_source("ui_next/qml/AppShell.qml")
        top = self._qml_source("ui_next/qml/components/TopStatusBar.qml")
        inspector = self._qml_source("ui_next/qml/components/RightInspector.qml")
        bottom = self._qml_source("ui_next/qml/components/BottomStatusBar.qml")

        self.assertNotIn("userFeatureSummary", shell)
        self.assertNotIn("modeLabel:", shell)
        self.assertNotIn("capabilityLabel:", shell)
        self.assertNotIn("modeStatusBadge", top)
        self.assertNotIn("capabilityStatusBadge", top)
        self.assertNotIn('label: "未监听"', top)
        self.assertNotIn('label: "无任务"', top)
        self.assertIn('"当前状态：" + root.runtimeLabel', inspector)
        self.assertIn('"可用功能：" + root.enabledFeatures', inspector)
        self.assertIn('"安全保护：" + root.safetySummary', inspector)
        self.assertNotIn('root.enabledCapabilities', inspector)
        self.assertIn('property string statusText: "就绪"', bottom)
        self.assertNotIn('旧 Widgets UI 未移除', bottom)

    def test_panels_keep_user_messages_primary_and_technical_details_secondary(self):
        scan = self._qml_source("ui_next/qml/components/ScanPreviewPanel.qml")
        convert = self._qml_source("ui_next/qml/components/SingleFileConvertPanel.qml")

        self.assertIn("扫描只读取目录；加入任务队列和开始转换都必须由用户显式操作", scan)
        self.assertIn("加入队列只创建任务参数快照", scan)
        self.assertNotIn("Phase 4.4", scan)
        self.assertIn("转换完成，输出文件已安全生成，未覆盖已有文件。", convert)
        self.assertIn("目标路径已被其他程序创建。为避免覆盖，本次输出未写入该路径。", convert)
        self.assertIn("查看详细信息", convert)
        self.assertIn("错误代码：", convert)
        self.assertIn("落位策略：", convert)

    def test_metadata_lyrics_and_cover_do_not_promote_internal_capability_names(self):
        metadata = self._qml_source("ui_next/qml/pages/MetadataPage.qml")
        metadata_form = self._qml_source(
            "ui_next/qml/components/MetadataForm.qml"
        )
        lyrics_editor = self._qml_source(
            "ui_next/qml/components/LyricsDraftEditor.qml"
        )
        lyrics = self._qml_source("ui_next/qml/pages/LyricsCoverPage.qml")
        cover = self._qml_source("ui_next/qml/components/CoverPreviewCard.qml")
        current_file = self._qml_source(
            "ui_next/qml/components/CurrentFileBar.qml"
        )

        self.assertIn(
            'metadataViewModel.metadataReadEnabled ? "仅查看" : "预览信息"',
            metadata,
        )
        self.assertIn('label: "未保存"', metadata_form)
        self.assertNotIn('label: "metadata_write"', metadata)
        self.assertIn("导入新的 .lrc 会替换当前内存中的歌词修改", lyrics)
        self.assertIn('objectName: "currentLyricsPane"', lyrics_editor)
        self.assertIn("导入音频", current_file)
        self.assertIn("封面可供查看；替换、移除和恢复请在文件信息页面作为草稿处理。", cover)
        self.assertNotIn('label: "cover_read"', cover)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "ui_next" / "qml"


def _read(relative_path: str) -> str:
    return (QML / relative_path).read_text(encoding="utf-8")


def test_global_dialog_is_the_only_editor_export_ui():
    dialog = _read("components/EditExportDialog.qml")
    shell = _read("AppShell.qml")
    current_file = _read("components/CurrentFileBar.qml")

    assert shell.count("EditExportDialog {") == 1
    assert 'objectName: "unifiedEditExportDialog"' in dialog
    assert 'openUnifiedExportDialog("auto")' in current_file
    assert 'text: "导出"' in current_file

    for relative_path in (
        "pages/MetadataPage.qml",
        "pages/LyricsCoverPage.qml",
        "components/MetadataForm.qml",
        "components/CoverDraftEditor.qml",
        "components/LyricsDraftEditor.qml",
        "components/PitchShiftCard.qml",
    ):
        content = _read(relative_path)
        assert "openUnifiedExportDialog" not in content, relative_path
        assert "requestExport()" not in content, relative_path


def test_dialog_aggregates_all_drafts_and_both_output_types():
    dialog = _read("components/EditExportDialog.qml")
    shell = _read("AppShell.qml")

    for marker in (
        "root.editSession.dirty",
        "root.editSession.lyricsDirty",
        "root.editSession.coverDirty",
        "root.editSession.processingDirty",
        "root.processingSelected = root.editSession.processingDirty",
        'setUnifiedExportTarget("audio")',
        'setUnifiedExportTarget("lrc")',
        "startUnifiedAudioExport",
        "startUnifiedLrcExport",
        'objectName: "editExportOverwriteConfirmDialog"',
        "unifiedExportOverwriteRequired",
        "unifiedExportOverwritesSource",
        "确认覆盖源文件",
        "切换文件前会导出全部未保存修改",
        "!root.selectAllDraftsOnOpen",
        "载入为当前文件",
        "复制路径",
        "打开位置",
    ):
        assert marker in dialog

    assert "processingSession: processingSessionViewModel" in shell
    assert "pitchDraftWarningDialog" not in shell


def test_editor_surfaces_only_mark_changed_sections_as_unsaved():
    current_file = _read("components/CurrentFileBar.qml")
    metadata = _read("components/MetadataForm.qml")
    cover = _read("components/CoverDraftEditor.qml")
    lyrics = _read("components/LyricsDraftEditor.qml")
    pitch = _read("components/PitchShiftCard.qml")

    for marker in (
        "文件信息 · 未保存",
        "封面 · 未保存",
        "歌词 · 未保存",
        "音频处理 · 未保存",
    ):
        assert marker in current_file

    for content in (metadata, cover, lyrics, pitch):
        assert 'label: "未保存"' in content
        assert "visible:" in content

    assert "保存草稿" not in _read("pages/MetadataPage.qml")
    assert "lyricsExportMenu" not in lyrics
    assert "pitchExportPane" not in pitch

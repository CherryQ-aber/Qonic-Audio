from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "ui_next" / "qml"


def test_global_dialog_is_the_only_audio_copy_export_ui():
    dialog = (QML / "components" / "EditExportDialog.qml").read_text(encoding="utf-8")
    shell = (QML / "AppShell.qml").read_text(encoding="utf-8")
    metadata = (QML / "pages" / "MetadataPage.qml").read_text(encoding="utf-8")
    lyrics_cover = (QML / "pages" / "LyricsCoverPage.qml").read_text(encoding="utf-8")
    audio_editor = (QML / "pages" / "AudioEditorPage.qml").read_text(encoding="utf-8")
    current_file = (QML / "components" / "CurrentFileBar.qml").read_text(encoding="utf-8")

    assert "objectName: \"unifiedEditExportDialog\"" in dialog
    assert "EditExportDialog" in shell
    assert 'openUnifiedExportDialog("metadata")' in metadata
    assert 'openUnifiedExportDialog("lyrics")' in lyrics_cover
    assert 'openUnifiedExportDialog("cover")' in metadata
    assert 'openUnifiedExportDialog("cover")' not in lyrics_cover
    assert 'openUnifiedExportDialog("auto")' in audio_editor + current_file
    assert "metadataCombinedExportDialog" not in metadata
    assert "combinedExportDialog" not in lyrics_cover
    assert "coverCombinedExportDialog" not in metadata


def test_dialog_exposes_dirty_scope_capability_and_safe_path_rules():
    dialog = (QML / "components" / "EditExportDialog.qml").read_text(encoding="utf-8")

    for marker in (
        "root.editSession.dirty",
        "root.editSession.lyricsDirty",
        "root.editSession.coverDirty",
        "metadataWriteEnabled",
        "lyricsWriteEnabled",
        "coverWriteEnabled",
        "输出必须是与源文件同扩展名的全新文件",
        "不会修改或覆盖当前源文件",
        "startUnifiedAudioExport",
        "复制输出路径",
        "打开输出位置",
    ):
        assert marker in dialog
    assert "覆盖原文件" not in dialog


def test_shared_export_result_is_visible_from_all_edit_surfaces():
    for relative_path in (
        "pages/MetadataPage.qml",
        "components/LyricsDraftEditor.qml",
        "components/CoverDraftEditor.qml",
        "components/RightInspector.qml",
    ):
        content = (QML / relative_path).read_text(encoding="utf-8")
        assert "unifiedExportMessage" in content, relative_path
        assert "unifiedExportResult" in content, relative_path

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "ui_next" / "qml"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_metadata_page_owns_cover_draft_controls():
    metadata = _read("ui_next/qml/pages/MetadataPage.qml")
    lyrics = _read("ui_next/qml/pages/LyricsCoverPage.qml")

    assert "CoverDraftEditor {" in metadata
    assert 'objectName: "metadataCoverEditor"' in metadata
    assert "chooseReplacementCover()" in metadata
    assert "removeCoverDraft()" in metadata
    assert "restoreOriginalCover()" in metadata
    assert 'openUnifiedExportDialog("cover")' in metadata

    assert "CoverDraftEditor {" not in lyrics
    assert "chooseReplacementCover" not in lyrics
    assert "removeCoverDraft" not in lyrics
    assert "restoreOriginalCover" not in lyrics
    assert 'openUnifiedExportDialog("cover")' not in lyrics


def test_lyrics_page_keeps_only_lyrics_state_and_actions():
    lyrics = _read("ui_next/qml/pages/LyricsCoverPage.qml")

    assert "lyricsViewModel" in lyrics
    assert "LyricsPreviewList" in lyrics
    assert "LyricsDraftEditor" in lyrics
    assert "chooseLyricsFile()" in lyrics
    assert 'openUnifiedExportDialog("lyrics")' in lyrics
    assert "coverViewModel" not in lyrics
    assert "coverDirty" not in lyrics
    assert "lastCoverExport" not in lyrics


def test_production_ui_uses_lyrics_name_without_legacy_visible_copy():
    app_state = _read("ui_next/bridge/app_state_viewmodel.py")
    source_label = _read("ui_next/bridge/file_session_viewmodel.py")
    production_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "ui_next").rglob("*"))
        if path.suffix in {".py", ".qml"}
    )

    assert '"title": "歌词"' in app_state
    assert '"lyrics_cover_page": "歌词"' in source_label
    assert "歌词 / 封面" not in production_text
    assert "歌词与封面" not in production_text


def test_single_cover_reader_feeds_the_shared_edit_session():
    main = _read("main_qml.py")

    assert main.count("cover_view_model = CoverViewModel(") == 1
    assert main.count('setContextProperty("coverViewModel", cover_view_model)') == 1
    assert "file_session_view_model.attach_readers(" in main
    assert "cover_view_model.coverReadApplied.connect(" in main
    assert "edit_session_view_model.loadCoverResult" in main
    assert "edit_session_view_model.loadMetadataResult" in main
    assert "edit_session_view_model.loadLyricsResult" in main
    assert "lambda: edit_session_view_model.hasUnsavedDrafts" in main


def test_unified_export_remains_the_single_audio_copy_dialog():
    shell = _read("ui_next/qml/AppShell.qml")
    dialog = _read("ui_next/qml/components/EditExportDialog.qml")

    assert shell.count("EditExportDialog {") == 1
    assert 'objectName: "unifiedEditExportDialog"' in dialog
    assert "startUnifiedAudioExport" in dialog
    assert "metadataDirty" not in _read("ui_next/qml/pages/LyricsCoverPage.qml")
    assert (QML / "pages" / "LyricsCoverPage.qml").is_file()


def test_lyrics_preview_and_draft_have_independent_vertical_scroll_areas():
    editor = _read("ui_next/qml/components/LyricsDraftEditor.qml")

    assert 'objectName: "originalLyricsScrollView"' in editor
    assert 'objectName: "originalLyricsTextArea"' in editor
    assert 'objectName: "originalLyricsVerticalScrollBar"' in editor
    assert 'objectName: "lyricsDraftScrollView"' in editor
    assert 'objectName: "lyricsDraftTextArea"' in editor
    assert 'objectName: "draftLyricsVerticalScrollBar"' in editor
    assert editor.count("contentWidth: availableWidth") == 2
    assert editor.count("ScrollBar.horizontal.policy: ScrollBar.AlwaysOff") == 2
    assert editor.count("ScrollBar.vertical: ThemeScrollBar {") == 2
    assert editor.count("policy: ScrollBar.AlwaysOn") == 2
    assert editor.count("Layout.rightMargin: root.theme.spacing") == 2
    assert "parent: originalLyricsScrollView" in editor
    assert "anchors.right: originalLyricsScrollView.right" in editor
    assert "parent: draftScrollView" in editor
    assert "anchors.right: draftScrollView.right" in editor
    assert "rightPadding: originalLyricsVerticalScrollBar.width + 4" in editor
    assert "rightPadding: draftLyricsVerticalScrollBar.width + 4" in editor
    assert "height: Math.max(implicitHeight, originalLyricsScrollView.availableHeight)" in editor
    assert "height: Math.max(implicitHeight, draftScrollView.availableHeight)" in editor

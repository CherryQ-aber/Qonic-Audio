import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer

from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.audio_processing_session import ProcessingSessionViewModel
from ui_next.bridge.capabilities import (
    AUDIO_EXPORT,
    AUDIO_PLAYBACK,
    AUDIO_PROCESSING,
    DEFAULT_USER_MODE,
    METADATA_WRITE,
    CapabilityGate,
)
from ui_next.bridge.edit_session import EditSessionViewModel
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel


class _FakeAudioOutput(QObject):
    def __init__(self):
        super().__init__()
        self.volume = 0.0
        self.muted = False

    def setVolume(self, value):
        self.volume = float(value)

    def setMuted(self, value):
        self.muted = bool(value)

    def isMuted(self):
        return self.muted

    def device(self):
        return None


class _FakePlayer(QObject):
    playbackStateChanged = Signal(object)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    mediaStatusChanged = Signal(object)
    errorOccurred = Signal(object, str)

    def __init__(self):
        super().__init__()
        self.source = QUrl()
        self.position = 0
        self.duration_value = 0
        self.play_count = 0
        self.set_source_count = 0

    def setAudioOutput(self, _output):
        return

    def setSource(self, source):
        self.source = source
        self.position = 0
        self.set_source_count += 1

    def play(self):
        self.play_count += 1
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)

    def pause(self):
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PausedState)

    def stop(self):
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)

    def setPosition(self, position):
        self.position = int(position)
        self.positionChanged.emit(self.position)

    def duration(self):
        return self.duration_value

    def errorString(self):
        return ""


def _build_player():
    gate = CapabilityGate(
        (AUDIO_PLAYBACK,),
        runtime_mode=DEFAULT_USER_MODE,
    )
    file_session = FileSessionViewModel(gate)
    backend = _FakePlayer()
    output = _FakeAudioOutput()
    player = AudioPlayerViewModel(
        file_session,
        gate,
        media_player=backend,
        audio_output=output,
    )
    return file_session, player, backend, output


def _audio(path: Path) -> str:
    path.write_bytes(b"audio")
    return str(path.resolve())


def _mark_loaded(player, backend, duration=600_000):
    backend.duration_value = int(duration)
    backend.durationChanged.emit(int(duration))
    backend.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
    assert player.playerState == "ready"


def _player_snapshot(player, backend):
    return (
        player.currentPlaybackSourcePath,
        player.currentPlaybackSourceType,
        player.playbackOrigin,
        player.position,
        player.playerState,
        player.mediaOperationBusy,
        backend.source.toLocalFile(),
        backend.set_source_count,
    )


def test_reload_is_reader_only_and_preserves_non_editor_playback(tmp_path):
    file_session, player, backend, _output = _build_player()
    editor = _audio(tmp_path / "editor.wav")
    transcode = _audio(tmp_path / "transcode.wav")
    changed = []
    reloaded = []
    playback_requests = []
    file_session.currentFileChanged.connect(
        lambda path, generation: changed.append((path, generation))
    )
    file_session.currentFileReloaded.connect(
        lambda path, generation: reloaded.append((path, generation))
    )
    file_session.editorFilePlaybackRequested.connect(
        lambda path, generation, origin: playback_requests.append(
            (path, generation, origin)
        )
    )

    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    assert player.setPlaybackSourceWithOrigin(
        transcode,
        "转码源文件",
        "unknown",
        "transcode_source",
        False,
        0,
    )
    _mark_loaded(player, backend)
    player.seek(3210)
    before = (
        player.currentPlaybackSourcePath,
        player.currentPlaybackSourceType,
        player.playbackOrigin,
        player.position,
        player.playerState,
        backend.set_source_count,
    )
    changed.clear()
    reloaded.clear()
    playback_requests.clear()

    file_session.reloadCurrentFile()

    assert changed == []
    assert reloaded == [(editor, file_session.sessionGeneration)]
    assert playback_requests == []
    assert (
        player.currentPlaybackSourcePath,
        player.currentPlaybackSourceType,
        player.playbackOrigin,
        player.position,
        player.playerState,
        backend.set_source_count,
    ) == before


@pytest.mark.parametrize(
    "origin",
    ["folder_tree", "transcode_source", "transcode_output"],
)
def test_clear_and_missing_keep_unrelated_playback_origins(tmp_path, origin):
    for action in ("clear", "missing"):
        file_session, player, backend, _output = _build_player()
        editor = _audio(tmp_path / f"{origin}-{action}-editor.wav")
        unrelated = _audio(tmp_path / f"{origin}-{action}-unrelated.wav")
        assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
        assert player.setPlaybackSourceWithOrigin(
            unrelated,
            origin,
            "unknown",
            origin,
            False,
            0,
        )
        before_count = backend.set_source_count

        if action == "clear":
            file_session.clearCurrentFile()
        else:
            file_session.markCurrentFileMissing()

        assert player.currentPlaybackSourcePath == unrelated
        assert player.playbackOrigin == origin
        assert backend.set_source_count == before_count


def test_legacy_export_result_type_is_not_assumed_to_be_editor_owned(tmp_path):
    file_session, player, backend, _output = _build_player()
    editor = _audio(tmp_path / "editor.wav")
    transcode_output = _audio(tmp_path / "converted.flac")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    assert player.setPlaybackSourceWithType(
        transcode_output,
        "转换结果",
        "export_result",
        False,
        0,
    )

    assert player.currentPlaybackSourceType == "export_result"
    assert player.playbackOrigin == "unknown"
    before_count = backend.set_source_count
    file_session.clearCurrentFile()

    assert player.currentPlaybackSourcePath == transcode_output
    assert player.playbackOrigin == "unknown"
    assert backend.set_source_count == before_count


@pytest.mark.parametrize("origin", ["editor_file", "editor_export", "pitch_preview"])
def test_clear_releases_editor_associated_playback_origins(tmp_path, origin):
    file_session, player, _backend, _output = _build_player()
    editor = _audio(tmp_path / f"{origin}-editor.wav")
    playback = (
        _audio(tmp_path / f"{origin}-playback.wav")
        if origin == "pitch_preview"
        else editor
    )
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    assert player.setPlaybackSourceWithOrigin(
        playback,
        origin,
        "preview_cache" if origin == "pitch_preview" else "original",
        origin,
        False,
        0,
    )

    file_session.clearCurrentFile()

    assert not player.hasPlaybackSource
    assert player.currentPlaybackSourcePath == ""


def test_media_operation_token_is_single_owner_and_blocks_source_switch(tmp_path):
    file_session, player, backend, _output = _build_player()
    editor = _audio(tmp_path / "editor.wav")
    other = _audio(tmp_path / "other.wav")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    _mark_loaded(player, backend)
    player.seek(12_345)
    player.play()
    play_count = backend.play_count

    token = player.beginFileOperation("edit_export")

    assert token
    assert player.mediaOperationBusy
    assert not player.hasPlaybackSource
    assert player.beginFileOperation("pitch_export") == ""
    assert not player.setPlaybackSourceWithOrigin(
        other,
        "转码源文件",
        "unknown",
        "transcode_source",
        False,
        0,
    )
    assert player.finishFileOperation(token, True)
    assert not player.mediaOperationBusy
    assert player.currentPlaybackSourcePath == editor
    assert player.position == 12_345
    assert player.playbackOrigin == "editor_file"
    assert backend.play_count == play_count


def test_wrong_expired_and_duplicate_tokens_cannot_end_an_operation(tmp_path):
    file_session, player, _backend, _output = _build_player()
    editor = _audio(tmp_path / "editor.wav")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"

    first = player.beginFileOperation("first")
    assert first
    assert not player.finishFileOperation("wrong-token", True)
    assert player.mediaOperationBusy
    assert player.finishFileOperation(first, False)
    assert not player.finishFileOperation(first, True)

    second = player.beginFileOperation("second")
    assert second and second != first
    assert not player.finishFileOperation(first, True)
    assert player.mediaOperationBusy
    assert player.finishFileOperation(second, False)


def test_empty_operation_snapshot_never_falls_back_to_file_session(tmp_path):
    file_session, player, backend, _output = _build_player()
    editor = _audio(tmp_path / "editor.wav")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    player.clear()
    source_count = backend.set_source_count

    token = player.beginFileOperation("no-source-export")

    assert token
    assert player.finishFileOperation(token, True)
    assert not player.hasPlaybackSource
    assert player.currentPlaybackSourcePath == ""
    assert backend.source.isEmpty()
    assert backend.set_source_count == source_count + 1


def test_unified_result_dirty_guard_cancel_is_a_complete_player_noop(tmp_path):
    gate = CapabilityGate(
        (AUDIO_PLAYBACK, METADATA_WRITE),
        runtime_mode=DEFAULT_USER_MODE,
    )
    file_session = FileSessionViewModel(gate)
    edit_session = EditSessionViewModel(gate)
    backend = _FakePlayer()
    player = AudioPlayerViewModel(
        file_session,
        gate,
        media_player=backend,
        audio_output=_FakeAudioOutput(),
    )
    edit_session.attach_runtime(file_session, player)
    file_session.currentFileChanged.connect(edit_session.beginCurrentFile)
    file_session.currentFileReloaded.connect(edit_session.beginCurrentFile)
    file_session.setUnsavedChangesGuard(
        lambda: edit_session.hasUnsavedDrafts
    )
    editor = _audio(tmp_path / "editor.flac")
    transcode = _audio(tmp_path / "transcode.wav")
    result = _audio(tmp_path / "edited.flac")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    edit_session.loadMetadataResult(
        {
            "ok": True,
            "path": editor,
            "session_generation": file_session.sessionGeneration,
            "title": "Old",
        }
    )
    edit_session.updateField("title", "New")
    edit_session._unified_export_result = {
        "success": True,
        "output_path": result,
    }
    assert player.setPlaybackSourceWithOrigin(
        transcode,
        "转码源文件",
        "unknown",
        "transcode_source",
        False,
        0,
    )
    _mark_loaded(player, backend)
    player.seek(7_654)
    before = _player_snapshot(player, backend)

    edit_session.loadUnifiedExportResultAsCurrent()

    assert file_session.hasPendingFileChange
    assert _player_snapshot(player, backend) == before
    file_session.cancelPendingFileChange()
    assert _player_snapshot(player, backend) == before
    assert edit_session.hasUnsavedDrafts


def test_pitch_result_dirty_guard_cancel_is_a_complete_player_noop(tmp_path):
    gate = CapabilityGate(
        (
            AUDIO_PLAYBACK,
            AUDIO_PROCESSING,
            AUDIO_EXPORT,
            METADATA_WRITE,
        ),
        runtime_mode=DEFAULT_USER_MODE,
    )
    file_session = FileSessionViewModel(gate)
    edit_session = EditSessionViewModel(gate)
    backend = _FakePlayer()
    player = AudioPlayerViewModel(
        file_session,
        gate,
        media_player=backend,
        audio_output=_FakeAudioOutput(),
    )
    file_session.currentFileChanged.connect(edit_session.beginCurrentFile)
    file_session.currentFileReloaded.connect(edit_session.beginCurrentFile)
    file_session.setUnsavedChangesGuard(
        lambda: edit_session.hasUnsavedDrafts
    )
    processing = ProcessingSessionViewModel(
        file_session,
        player,
        edit_session,
        gate,
    )
    editor = _audio(tmp_path / "editor.wav")
    transcode = _audio(tmp_path / "transcode.wav")
    result = _audio(tmp_path / "pitch.wav")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    edit_session.loadMetadataResult(
        {
            "ok": True,
            "path": editor,
            "session_generation": file_session.sessionGeneration,
            "title": "Old",
        }
    )
    edit_session.updateField("title", "New")
    processing._export_path = result
    processing._export_result = {
        "success": True,
        "output_path": result,
    }
    assert player.setPlaybackSourceWithOrigin(
        transcode,
        "转码源文件",
        "unknown",
        "transcode_source",
        False,
        0,
    )
    _mark_loaded(player, backend)
    player.seek(4_321)
    before = _player_snapshot(player, backend)

    processing.loadExportResultAsCurrent()

    assert file_session.hasPendingFileChange
    assert _player_snapshot(player, backend) == before
    file_session.cancelPendingFileChange()
    assert _player_snapshot(player, backend) == before
    assert edit_session.hasUnsavedDrafts


def test_playback_properties_timestamp_seek_and_unknown_origin(tmp_path):
    file_session, player, backend, output = _build_player()
    editor = _audio(tmp_path / "editor.wav")
    other = _audio(tmp_path / "other.wav")
    assert file_session.setCurrentFile(editor, "audio_editor") == "loaded"
    _mark_loaded(player, backend, duration=4_000_000)
    backend.positionChanged.emit(201_450)

    assert player.hasPlaybackSource
    assert player.currentPlaybackFileName == "editor.wav"
    assert player.playbackMatchesEditorFile
    assert player.playbackOrigin == "editor_file"
    assert player.seekStepMs == 2000
    assert player.currentTimestampText == "[03:21.45]"

    player.seekBackward()
    assert player.position == 199_450
    player.seekForward()
    assert player.position == 201_450
    player.setMuted(True)
    assert player.muted
    assert output.muted

    assert player.setPlaybackSourceWithOrigin(
        other,
        "未知来源",
        "not-a-source-type",
        "not-an-origin",
        False,
        0,
    )
    assert player.currentPlaybackSourceType == "unknown"
    assert player.playbackOrigin == "unknown"
    assert not player.playbackMatchesEditorFile
    _mark_loaded(player, backend, duration=4_000_000)
    backend.positionChanged.emit(3_753_450)
    assert player.currentTimestampText == "[62:33.45]"


def test_file_session_signal_matrix_and_result_same_path_dirty_guard(tmp_path):
    gate = CapabilityGate((), runtime_mode=DEFAULT_USER_MODE)
    file_session = FileSessionViewModel(gate)
    first = _audio(tmp_path / "first.wav")
    second = _audio(tmp_path / "second.wav")
    third = _audio(tmp_path / "third.wav")
    changed = []
    reloaded = []
    playback_requests = []
    events = []
    file_session.currentFileChanged.connect(
        lambda path, generation: (
            changed.append((path, generation)),
            events.append(("changed", path, generation)),
        )
    )
    file_session.currentFileReloaded.connect(
        lambda path, generation: reloaded.append((path, generation))
    )
    file_session.editorFilePlaybackRequested.connect(
        lambda path, generation, origin: (
            playback_requests.append((path, generation, origin)),
            events.append(("playback", path, generation, origin)),
        )
    )

    assert file_session.setCurrentFile(first, "audio_editor") == "loaded"
    assert changed[-1][0] == first
    assert playback_requests[-1][0::2] == (first, "editor_file")
    assert [event[0] for event in events[:2]] == ["changed", "playback"]

    changed.clear()
    playback_requests.clear()
    events.clear()
    assert file_session.setCurrentFile(first, "audio_editor") == "unchanged"
    assert changed == []
    assert playback_requests[-1][0::2] == (first, "editor_file")

    playback_requests.clear()
    file_session.reloadCurrentFile()
    assert reloaded[-1][0] == first
    assert playback_requests == []

    file_session.setUnsavedChangesGuard(lambda: True)
    assert (
        file_session.setCurrentFile(second, "edit_export_result")
        == "confirmation_required"
    )
    assert playback_requests == []
    file_session.cancelPendingFileChange()
    assert playback_requests == []

    assert (
        file_session.setCurrentFile(first, "pitch_export_result")
        == "confirmation_required"
    )
    reload_count = len(reloaded)
    changed_count = len(changed)
    file_session.discardPendingFileChange()
    assert len(changed) == changed_count
    assert len(reloaded) == reload_count + 1
    assert playback_requests[-1][0::2] == (first, "editor_export")

    file_session.setUnsavedChangesGuard(None)
    playback_requests.clear()
    assert (
        file_session.setCurrentFile(second, "edit_export_result")
        == "loaded"
    )
    assert playback_requests[-1][0::2] == (second, "editor_export")
    playback_requests.clear()
    assert (
        file_session.setCurrentFile(second, "pitch_export_result")
        == "unchanged"
    )
    assert playback_requests[-1][0::2] == (second, "editor_export")

    file_session.setFileChangeBlocker(lambda: True)
    playback_requests.clear()
    assert file_session.setCurrentFile(third, "audio_editor") == "blocked"
    assert playback_requests == []
    file_session.setFileChangeBlocker(None)
    assert file_session.setCurrentFile(str(tmp_path / "missing.wav")) == "rejected"
    assert playback_requests == []


def test_main_registers_one_union_file_change_blocker():
    source = (
        Path(__file__).resolve().parents[1] / "main_qml.py"
    ).read_text(encoding="utf-8")

    assert source.count("setFileChangeBlocker(") == 1
    assert "edit_session_view_model.anyExporting" in source
    assert "processing_session_view_model.isBusy" in source
    assert "audio_player_view_model.mediaOperationBusy" in source

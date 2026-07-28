from pathlib import Path


def test_pitch_qml_uses_processing_session_not_mock_controls():
    root = Path(__file__).resolve().parents[1]
    card = (root / "ui_next/qml/components/PitchShiftCard.qml").read_text(encoding="utf-8")
    assert "processingSession" in card
    assert "模拟试听" not in card
    assert "试听当前设置" in card
    assert "导出为新文件" not in card
    assert "清理试听缓存" in card


def test_pitch_qml_renders_backend_terminal_states_and_decouples_preview_ready_from_playback():
    root = Path(__file__).resolve().parents[1]
    card = (root / "ui_next/qml/components/PitchShiftCard.qml").read_text(encoding="utf-8")
    for state in ("validating_request", "starting_process", "rendering", "waiting_process_exit", "validating_preview", "loading_player_source", "preview_ready", "cancelled", "error"):
        assert f'"{state}"' in card
    assert "播放试听" in card and "root.processingSession.playPreview()" in card
    assert "indeterminate: root.processingSession && root.processingSession.isBusy" in card


def test_pitch_qml_shows_real_stage_detail_and_cache_hit_without_fake_progress():
    root = Path(__file__).resolve().parents[1]
    card = (root / "ui_next/qml/components/PitchShiftCard.qml").read_text(encoding="utf-8")
    assert "root.processingSession.progressDetail" in card
    assert "root.processingSession.previewCacheHit" in card
    assert "root.processingSession.progress <= 0" in card

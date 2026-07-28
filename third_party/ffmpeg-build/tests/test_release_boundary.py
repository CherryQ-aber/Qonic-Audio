from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_build_scripts_do_not_write_formal_runtime():
    for path in list((ROOT / "scripts").glob("*.py")) + [
        ROOT / "build.sh",
        ROOT / "build.ps1",
    ]:
        text = path.read_text(encoding="utf-8").replace("\\", "/").lower()
        assert "tools/ffmpeg/bin" not in text


def test_only_candidate_output_is_named_by_builder():
    text = (ROOT / "scripts" / "build_ffmpeg.py").read_text(encoding="utf-8")
    assert 'OUTPUT / "candidate"' in text
    assert "copy2(source, target)" in text


def test_windows_wrapper_uses_native_exit_code_for_ffmpeg_captures():
    text = (ROOT / "build.ps1").read_text(encoding="utf-8")
    assert '$ErrorActionPreference = "Continue"' in text
    assert "$captureExitCode = $LASTEXITCODE" in text
    assert "if ($captureExitCode -ne 0)" in text

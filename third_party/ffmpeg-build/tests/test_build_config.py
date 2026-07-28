import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def flags():
    data = json.loads((ROOT / "config" / "feature-profile.json").read_text(encoding="utf-8"))
    return data["configure_flags"]


def test_config_is_allowlist_and_gpl():
    configured = flags()
    assert "--disable-everything" in configured
    assert "--disable-autodetect" in configured
    assert "--enable-gpl" in configured
    assert "--enable-version3" in configured
    assert "--disable-nonfree" in configured
    assert "--enable-nonfree" not in configured


def test_required_external_libraries_are_enabled():
    configured = flags()
    for name in ("zlib", "libmp3lame", "libvorbis", "libopus", "librubberband"):
        assert f"--enable-{name}" in configured


def test_raw_waveform_pipe_muxer_is_enabled():
    configured = "\n".join(flags())
    muxer_line = next(line for line in flags() if line.startswith("--enable-muxer="))
    assert "pcm_s16le" in muxer_line.split("=", 1)[1].split(",")
    assert "--enable-protocol=file,pipe" in configured


def test_network_and_unneeded_video_encoders_are_not_enabled():
    rendered = "\n".join(flags())
    assert "--disable-network" in rendered
    for forbidden in ("libx264", "libx265", "libvpx", "openssl", "gnutls"):
        assert f"--enable-{forbidden}" not in rendered


def test_mingw_environment_disables_glibc_fortify_wrappers():
    text = (ROOT / "scripts" / "common.py").read_text(encoding="utf-8")
    assert '"CPPFLAGS": f"-D_FORTIFY_SOURCE=0 ' in text

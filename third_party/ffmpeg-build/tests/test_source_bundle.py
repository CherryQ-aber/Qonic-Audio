from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_source_bundle_includes_reconstruction_materials():
    text = (ROOT / "scripts" / "generate_source_bundle.py").read_text(encoding="utf-8")
    for item in ("lock", "config", "scripts", "patches", "tests", "LICENSE_MATERIALS"):
        assert item in text
    assert "SOURCES.iterdir()" in text
    assert "SOURCE_OFFER.md" in text
    assert "build.ps1" in text
    assert "verify.ps1" in text

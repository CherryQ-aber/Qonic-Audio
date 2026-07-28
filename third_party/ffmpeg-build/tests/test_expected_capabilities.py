import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
BUILD = REPO / "third_party" / "ffmpeg-build"


def test_feature_requirements_are_represented_by_configure_lock():
    requirements = json.loads(
        (REPO / "compliance" / "report" / "ffmpeg-self-build" / "qonic-ffmpeg-feature-requirements.json").read_text(encoding="utf-8")
    )
    configured = "\n".join(
        json.loads((BUILD / "config" / "feature-profile.json").read_text(encoding="utf-8"))["configure_flags"]
    )
    for filter_name in requirements["required_filters"]:
        assert filter_name in configured
    for protocol in requirements["required_protocols"]:
        assert protocol in configured


def test_runtime_paths_remain_compatible():
    requirements = json.loads(
        (REPO / "compliance" / "report" / "ffmpeg-self-build" / "qonic-ffmpeg-feature-requirements.json").read_text(encoding="utf-8")
    )
    assert requirements["runtime_paths"]["ffmpeg"] == "Tools/ffmpeg/bin/ffmpeg.exe"
    assert requirements["runtime_paths"]["ffprobe"] == "Tools/ffmpeg/bin/ffprobe.exe"

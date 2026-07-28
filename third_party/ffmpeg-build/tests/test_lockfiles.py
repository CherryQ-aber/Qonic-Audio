import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCKS = ROOT / "lock"


def load(name):
    return json.loads((LOCKS / name).read_text(encoding="utf-8"))


def test_sources_have_exact_hashes_and_nonfloating_urls():
    floating = re.compile(
        r"(?:refs/heads/(?:main|master)|/(?:latest|head|rolling|current)(?:/|$)|snapshot)",
        re.IGNORECASE,
    )
    for source in load("sources.lock.json")["sources"]:
        assert source["version"]
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        assert not floating.search(source["url"])


def test_environment_is_digest_and_snapshot_locked():
    lock = load("build-environment.lock.json")
    image = lock["host_container"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", image["index_digest"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", image["linux_amd64_manifest_digest"])
    assert "20260713T000000Z" in lock["apt_snapshot"]["debian"]
    assert all(version and version not in {"latest", "*"} for version in lock["direct_packages"].values())


def test_nonfree_is_forbidden():
    policy = load("licenses.lock.json")["license_policy"]
    assert policy["gpl_allowed"] is True
    assert policy["nonfree_allowed"] is False

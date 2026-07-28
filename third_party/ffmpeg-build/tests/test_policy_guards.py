import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_source_entries_satisfy_declared_schema_contract():
    required = set(
        load(ROOT / "lock" / "sources.lock.schema.json")["properties"]["sources"]["items"]["required"]
    )
    for source in load(ROOT / "lock" / "sources.lock.json")["sources"]:
        assert required <= set(source)
        assert source["source_available"] is True
        assert source["license"] != "UNKNOWN"


def test_patches_are_empty_or_hash_locked():
    for source in load(ROOT / "lock" / "sources.lock.json")["sources"]:
        for patch in source["patches"]:
            assert re.fullmatch(r"[0-9a-f]{64}", patch["sha256"])
            assert patch["filename"]


def test_static_dependencies_have_source_and_license_records():
    sources = {item["name"]: item for item in load(ROOT / "lock" / "sources.lock.json")["sources"]}
    dependencies = load(ROOT / "lock" / "licenses.lock.json")["dependencies"]
    for dependency in dependencies:
        source = sources[dependency["name"]]
        assert source["source_available"] is True
        assert source["license_files"]
        assert source["static_linked"] is True


def test_configure_text_matches_machine_profile():
    expected = load(ROOT / "config" / "feature-profile.json")["configure_flags"]
    actual = [
        line.strip()
        for line in (ROOT / "config" / "ffmpeg-configure.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert actual == expected


def test_archive_extractor_has_path_traversal_guard():
    text = (ROOT / "scripts" / "prepare_sources.py").read_text(encoding="utf-8")
    assert "archive_path.is_absolute()" in text
    assert '".." in archive_path.parts' in text
    assert "archive path escapes workspace" in text
    assert "member.isdir() or member.isfile()" in text
    assert 'filter="data"' not in text


def test_build_manifest_records_environment_hashes_and_dlls():
    text = (ROOT / "scripts" / "generate_build_manifest.py").read_text(encoding="utf-8")
    for required in ("dpkg-query", "imported_dlls", "lockfiles", "SOURCE_INDEX.json", "SHA256SUMS.txt"):
        assert required in text


def test_no_obvious_secret_or_private_key_material_in_build_definition():
    patterns = (
        "BEGIN PRIVATE KEY",
        "ghp_",
        "sk-proj-",
        "api_key=",
        "authorization: bearer",
    )
    paths = list((ROOT / "scripts").glob("*.py"))
    paths += list((ROOT / "config").glob("*"))
    paths += list((ROOT / "lock").glob("*.json"))
    for path in paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            assert not any(pattern.lower() in text for pattern in patterns)


def test_logs_are_not_part_of_source_bundle_inputs():
    text = (ROOT / "scripts" / "generate_source_bundle.py").read_text(encoding="utf-8")
    assert '"work"' not in text
    assert '"output"' not in text


def test_source_bundle_excludes_python_bytecode():
    text = (ROOT / "scripts" / "generate_source_bundle.py").read_text(encoding="utf-8")
    assert '"__pycache__" in parts' in text
    assert 'info.name.endswith((".pyc", ".pyo", ".bak"))' in text
    assert "filter=source_bundle_filter" in text

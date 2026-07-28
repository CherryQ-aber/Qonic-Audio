"""Run the B4 Windows regression against an isolated PyInstaller onedir.

The authoritative expanded release is read-only.  The isolated copy must differ
from it only at the two FFmpeg executables before the packaged smoke tests run.
All media fixtures are synthetic.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


EXPECTED = {
    "archive": "649E38524AF2F3DCE33FCBC43AC29B7111623D033F3537DE55EF5CD45994E926",
    "formal_ffmpeg": "09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73",
    "formal_ffprobe": "A6618E99BB58869DED3C6F37B53AA1A8D701C3591DBB7B5B317D47369C112BE2",
    "candidate_ffmpeg": "CA2BCCBF1A2A5A379AE484AD127D120CC3E394833B69767694A1E738F2D6BE55",
    "candidate_ffprobe": "4EC2AC9385AACBAF927B7E8D031291059CEA2E02EE6BFAE0D708F78E1C528251",
}

TOOL_RELATIVE = {
    "ffmpeg": Path("_internal/Tools/ffmpeg/bin/ffmpeg.exe"),
    "ffprobe": Path("_internal/Tools/ffmpeg/bin/ffprobe.exe"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run(command: list[str | os.PathLike[str]], *, timeout: float = 120, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [os.fspath(item) for item in command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class Recorder:
    def __init__(self) -> None:
        self.tests: list[dict] = []

    def add(self, name: str, passed: bool, detail: str = "", **evidence) -> None:
        self.tests.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail,
                "evidence": evidence,
            }
        )
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    def blocked(self, name: str, detail: str, **evidence) -> None:
        self.tests.append(
            {"name": name, "status": "blocked", "detail": detail, "evidence": evidence}
        )
        print(f"[BLOCKED] {name}: {detail}")


def package_files(root: Path) -> dict[str, Path]:
    return {
        item.relative_to(root).as_posix(): item
        for item in root.rglob("*")
        if item.is_file()
    }


def verify_isolation(baseline: Path, isolated: Path, recorder: Recorder) -> None:
    baseline_files = package_files(baseline)
    isolated_files = package_files(isolated)
    same_names = set(baseline_files) == set(isolated_files)
    recorder.add(
        "isolated_package_file_set",
        same_names,
        f"baseline={len(baseline_files)}, isolated={len(isolated_files)}",
    )
    if not same_names:
        return

    allowed = {path.as_posix() for path in TOOL_RELATIVE.values()}
    unexpected: list[str] = []
    for relative in sorted(baseline_files):
        if relative in allowed:
            continue
        if sha256(baseline_files[relative]) != sha256(isolated_files[relative]):
            unexpected.append(relative)
    recorder.add(
        "isolated_package_only_ffmpeg_changed",
        not unexpected,
        "all non-FFmpeg files byte-identical" if not unexpected else f"unexpected={len(unexpected)}",
        unexpected_paths=unexpected[:20],
    )


def check_hashes(paths: dict[str, Path], recorder: Recorder, prefix: str) -> dict[str, str]:
    actual = {name: sha256(path) for name, path in paths.items()}
    for name, value in actual.items():
        recorder.add(
            f"{prefix}_{name}_hash",
            value == EXPECTED[name],
            value,
            expected=EXPECTED[name],
        )
    return actual


def must_run(command: list[str | os.PathLike[str]], label: str, timeout: float = 120) -> None:
    result = run(command, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{label} failed ({result.returncode}): {(result.stderr or result.stdout)[-1000:]}")


def generate_fixtures(
    gyan_ffmpeg: Path,
    mac_exe: Path | None,
    fixture_dir: Path,
    recorder: Recorder,
) -> dict[str, Path]:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    master = fixture_dir / "master.wav"
    must_run(
        [
            gyan_ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=3",
            "-filter:a",
            "volume=0.2",
            "-c:a",
            "pcm_s16le",
            master,
        ],
        "generate master WAV",
    )
    recipes = {
        "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
        "flac": ["-c:a", "flac"],
        "aac": ["-c:a", "aac", "-f", "adts"],
        "m4a": ["-c:a", "aac"],
        "ogg": ["-c:a", "libvorbis"],
        "opus": ["-c:a", "libopus"],
        "aiff": ["-c:a", "pcm_s16be"],
        "alac": ["-c:a", "alac", "-f", "ipod"],
        "wma": ["-c:a", "wmav2"],
    }
    fixtures = {"wav": master}
    for extension, arguments in recipes.items():
        output = fixture_dir / f"input.{extension}"
        must_run(
            [gyan_ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", master, *arguments, output],
            f"generate {extension}",
        )
        fixtures[extension] = output

    if mac_exe and mac_exe.is_file():
        ape = fixture_dir / "input.ape"
        result = run([mac_exe, master, ape, "-c2000"])
        if result.returncode == 0 and ape.is_file():
            fixtures["ape"] = ape
            recorder.add("synthetic_ape_fixture", True, "official MAC.exe encoded the synthetic WAV")
        else:
            recorder.blocked("synthetic_ape_fixture", "official MAC.exe did not create the fixture")
    else:
        recorder.blocked("synthetic_ape_fixture", "official MAC.exe path was not supplied")

    cover = fixture_dir / "cover.jpg"
    must_run(
        [
            gyan_ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=0.1",
            "-frames:v",
            "1",
            cover,
        ],
        "generate cover",
    )
    tagged_audio = fixture_dir / "tagged-audio.mp3"
    must_run(
        [
            gyan_ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            master,
            "-c:a",
            "libmp3lame",
            "-metadata",
            "title=Qonic B4 synthetic",
            "-metadata",
            "artist=CherryQ Studio",
            "-metadata",
            "album=B4 Regression",
            "-metadata",
            "lyrics=[00:00.00]synthetic lyric",
            tagged_audio,
        ],
        "generate tagged audio",
    )
    tagged_cover = fixture_dir / "tagged-cover.mp3"
    must_run(
        [
            gyan_ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            tagged_audio,
            "-i",
            cover,
            "-map",
            "0:a:0",
            "-map",
            "1:v:0",
            "-c",
            "copy",
            "-id3v2_version",
            "3",
            "-metadata:s:v",
            "title=Album cover",
            "-metadata:s:v",
            "comment=Cover (front)",
            tagged_cover,
        ],
        "attach cover",
    )
    fixtures["tagged_cover"] = tagged_cover
    recorder.add("synthetic_fixture_generation", True, f"formats={len(fixtures) - 1}")
    return fixtures


def probe_json(ffprobe: Path, media: Path) -> dict:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size:format_tags:stream=codec_type,codec_name:stream_disposition=attached_pic:stream_tags",
            "-of",
            "json",
            media,
        ]
    )
    if result.returncode:
        return {}
    return json.loads(result.stdout or "{}")


def test_candidate_media(
    candidate_ffmpeg: Path,
    candidate_ffprobe: Path,
    fixtures: dict[str, Path],
    output_dir: Path,
    recorder: Recorder,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_formats = ["mp3", "flac", "wav", "m4a", "aac", "ogg", "opus", "ape", "aiff", "alac", "wma"]
    for format_name in input_formats:
        source = fixtures.get(format_name)
        if not source:
            recorder.blocked(f"decode_{format_name}", "synthetic fixture unavailable")
            continue
        result = run([candidate_ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", source, "-f", "null", "-"])
        recorder.add(f"decode_{format_name}", result.returncode == 0, f"exit={result.returncode}")

    recipes = {
        "mp3": ["-c:a", "libmp3lame"],
        "flac": ["-c:a", "flac"],
        "wav": ["-c:a", "pcm_s16le"],
        "aac": ["-c:a", "aac", "-f", "adts"],
        "m4a": ["-c:a", "aac", "-f", "ipod"],
        "ogg": ["-c:a", "libvorbis"],
        "opus": ["-c:a", "libopus"],
    }
    for target, arguments in recipes.items():
        output = output_dir / f"candidate-output.{target}"
        result = run(
            [candidate_ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", fixtures["wav"], *arguments, output]
        )
        probe = probe_json(candidate_ffprobe, output) if result.returncode == 0 else {}
        recorder.add(
            f"encode_{target}",
            result.returncode == 0 and output.stat().st_size > 0 and bool(probe),
            f"exit={result.returncode}, bytes={output.stat().st_size if output.exists() else 0}",
        )


def test_project_apis(
    project_root: Path,
    candidate_ffmpeg: Path,
    candidate_ffprobe: Path,
    fixtures: dict[str, Path],
    output_dir: Path,
    recorder: Recorder,
) -> None:
    sys.path.insert(0, str(project_root))
    import converter
    import single_file_convert
    from ui_next.bridge.audio_processing_service import AudioProcessingService

    output_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(single_file_convert, "FFMPEG_PATH", str(candidate_ffmpeg)):
        for extension in ("mp3", "flac", "wav", "m4a", "aac", "ogg", "opus", "ape", "aiff", "alac", "wma"):
            if extension not in fixtures:
                continue
            destination = output_dir / f"single-{extension}.flac"
            result = single_file_convert.convert_single_file_to_new_path(
                str(fixtures[extension]), str(destination), "flac"
            )
            recorder.add(
                f"single_convert_{extension}",
                bool(result.get("ok")) and destination.is_file(),
                str(result.get("error_code") or "ok"),
            )

        corrupt = output_dir / "corrupt-input.mp3"
        corrupt.write_bytes(b"not an audio file")
        corrupt_result = single_file_convert.convert_single_file_to_new_path(
            str(corrupt), str(output_dir / "corrupt-output.flac"), "flac"
        )
        recorder.add(
            "corrupt_input_rejected",
            not corrupt_result.get("ok") and not (output_dir / "corrupt-output.flac").exists(),
            str(corrupt_result.get("error_code") or ""),
        )

        unicode_dir = output_dir / "中文 空格 Ω"
        unicode_dir.mkdir(parents=True, exist_ok=True)
        unicode_input = unicode_dir / "合成 输入.mp3"
        shutil.copy2(fixtures["mp3"], unicode_input)
        unicode_output = unicode_dir / "合成 输出.flac"
        unicode_result = single_file_convert.convert_single_file_to_new_path(
            str(unicode_input), str(unicode_output), "flac"
        )
        recorder.add("unicode_and_space_paths", bool(unicode_result.get("ok")), str(unicode_result.get("error_code") or "ok"))

        long_dir = output_dir
        while len(str(long_dir / "input.mp3")) < 280:
            long_dir = long_dir / "long-path-segment-0123456789"
        long_dir.mkdir(parents=True, exist_ok=True)
        long_input = long_dir / "input.mp3"
        long_output = long_dir / "output.flac"
        shutil.copy2(fixtures["mp3"], long_input)
        long_result = single_file_convert.convert_single_file_to_new_path(
            str(long_input), str(long_output), "flac"
        )
        recorder.add("long_path_over_260", bool(long_result.get("ok")), f"path_length={len(str(long_output))}")

        cross_root = Path(tempfile.gettempdir()) / f"qonic-b4-cross-drive-{os.getpid()}"
        cross_root.mkdir(parents=True, exist_ok=True)
        cross_output = cross_root / "cross-drive.flac"
        cross_result = single_file_convert.convert_single_file_to_new_path(
            str(fixtures["mp3"]), str(cross_output), "flac"
        )
        recorder.add(
            "cross_drive_output",
            bool(cross_result.get("ok")),
            f"source_drive={fixtures['mp3'].drive}, output_drive={cross_output.drive}",
        )

    with patch.object(converter, "FFMPEG_PATH", str(candidate_ffmpeg)):
        batch_root = output_dir / "batch"
        batch_results = [
            converter.convert_audio(
                str(fixtures[source]),
                "wav",
                output_root_override=str(batch_root),
                create_format_subfolder=False,
                safe_publish=True,
            )
            for source in ("mp3", "flac")
        ]
        recorder.add(
            "manual_multi_item_queue_engine",
            all(result.get("success") for result in batch_results),
            f"successes={sum(bool(item.get('success')) for item in batch_results)}/2",
        )

        cancel_event = threading.Event()
        timer = threading.Timer(0.3, cancel_event.set)
        timer.start()
        cancel_command = [
            str(candidate_ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-re",
            "-i",
            str(fixtures["wav"]),
            "-f",
            "null",
            "-",
        ]
        try:
            converter._run_cancellable_ffmpeg_command(cancel_command, cancel_event)
            cancelled = False
        except converter.ConversionCancelled:
            cancelled = True
        finally:
            timer.cancel()
        recorder.add("queue_cancel_reaps_ffmpeg", cancelled, "cancelled child was reaped")

    service = AudioProcessingService(str(candidate_ffmpeg))
    preview = output_dir / "pitch-preview-minus-2.wav"
    preview_result = service.render_pitch_shift(
        str(fixtures["mp3"]), str(preview), -2, preview=True, request_id="b4-preview"
    )
    recorder.add(
        "pitch_preview_negative",
        bool(preview_result.get("success")) and preview.is_file(),
        str(preview_result.get("error_code") or "ok"),
    )

    for semitone in (-2, 2):
        export = output_dir / f"pitch-export-{semitone:+d}.mp3"
        result = service.render_pitch_shift(
            str(fixtures["tagged_cover"]),
            str(export),
            semitone,
            preview=False,
            request_id=f"b4-export-{semitone}",
        )
        data = probe_json(candidate_ffprobe, export) if result.get("success") else {}
        tags = {str(key).lower(): value for key, value in data.get("format", {}).get("tags", {}).items()}
        has_cover = any(
            stream.get("codec_type") == "video"
            and int(stream.get("disposition", {}).get("attached_pic", 0)) == 1
            for stream in data.get("streams", [])
        )
        preserved = tags.get("title") == "Qonic B4 synthetic" and tags.get("artist") == "CherryQ Studio"
        recorder.add(
            f"pitch_export_{semitone:+d}_metadata_cover",
            bool(result.get("success")) and preserved and has_cover,
            f"success={bool(result.get('success'))}, metadata={preserved}, cover={has_cover}",
            tags=tags,
        )


@contextmanager
def exclusive_read_lock(path: Path):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,
        0,
        None,
        3,
        0x80,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateFileW failed")
    try:
        yield
    finally:
        kernel32.CloseHandle(handle)


def test_occupied_file(candidate_ffmpeg: Path, fixture: Path, recorder: Recorder) -> None:
    with exclusive_read_lock(fixture):
        result = run([candidate_ffmpeg, "-hide_banner", "-loglevel", "error", "-i", fixture, "-f", "null", "-"])
    recorder.add("occupied_input_fails_cleanly", result.returncode != 0, f"exit={result.returncode}")


def test_packaged_smoke(isolated: Path, recorder: Recorder) -> None:
    executable = isolated / "Qonic_Audio_v5.0_internal_test.exe"
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "CHERRYQ_QML_USER_TEST": "1",
            "QONIC_QML_USER_TEST": "1",
        }
    )
    for module in ("audioEditor", "autoConvert", "settings"):
        result = run(
            [executable, "--qml-smoke-test", f"--qml-open-module={module}"],
            timeout=90,
            env=environment,
        )
        recorder.add(
            f"packaged_smoke_{module}",
            result.returncode == 0,
            f"exit={result.returncode}",
            stderr_tail=(result.stderr or "")[-500:],
        )


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=project_root / "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test",
    )
    parser.add_argument(
        "--isolated",
        type=Path,
        default=project_root / "third_party/ffmpeg-build/output/b4-isolated/2026-07-28/Qonic_Audio_v5.0_internal_test",
    )
    parser.add_argument("--mac-exe", type=Path)
    parser.add_argument(
        "--report",
        type=Path,
        default=project_root / "compliance/report/ffmpeg-self-build/b4-regression-report.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    baseline = args.baseline.resolve()
    isolated = args.isolated.resolve()
    report_path = args.report.resolve()
    recorder = Recorder()
    started = datetime.now(timezone.utc)
    run_root = project_root / "third_party/ffmpeg-build/output/b4-evidence" / started.strftime("%Y-%m-%dT%H%M%SZ")
    fixture_dir = run_root / "fixtures"
    output_dir = run_root / "outputs"

    formal_paths = {
        "archive": project_root / "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z",
        "formal_ffmpeg": project_root / "Tools/ffmpeg/bin/ffmpeg.exe",
        "formal_ffprobe": project_root / "Tools/ffmpeg/bin/ffprobe.exe",
    }
    isolated_paths = {
        "candidate_ffmpeg": isolated / TOOL_RELATIVE["ffmpeg"],
        "candidate_ffprobe": isolated / TOOL_RELATIVE["ffprobe"],
    }
    before = check_hashes(formal_paths, recorder, "before")
    check_hashes(isolated_paths, recorder, "isolated")
    verify_isolation(baseline, isolated, recorder)

    fixtures = generate_fixtures(
        formal_paths["formal_ffmpeg"],
        args.mac_exe.resolve() if args.mac_exe else None,
        fixture_dir,
        recorder,
    )
    test_candidate_media(
        isolated_paths["candidate_ffmpeg"],
        isolated_paths["candidate_ffprobe"],
        fixtures,
        output_dir / "direct",
        recorder,
    )
    test_project_apis(
        project_root,
        isolated_paths["candidate_ffmpeg"],
        isolated_paths["candidate_ffprobe"],
        fixtures,
        output_dir / "project-api",
        recorder,
    )
    test_occupied_file(isolated_paths["candidate_ffmpeg"], fixtures["mp3"], recorder)
    test_packaged_smoke(isolated, recorder)

    after = check_hashes(formal_paths, recorder, "after")
    recorder.add("formal_boundaries_unchanged", before == after, "archive and formal tools unchanged")

    counts = {
        status: sum(item["status"] == status for item in recorder.tests)
        for status in ("pass", "fail", "blocked")
    }
    overall = "pass" if counts["fail"] == 0 and counts["blocked"] == 0 else "fail"
    report = {
        "schema_version": 1,
        "phase": "B4",
        "overall_status": overall,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "release_baseline": "Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z",
        "isolated_package": isolated.relative_to(project_root).as_posix(),
        "fixture_policy": "synthetic-only",
        "monkey_audio_fixture_tool": {
            "version": "13.20",
            "source": "https://monkeysaudio.com/x64",
            "installer_sha256": "091931DC828ADE7A7EC3ABB380D8612FCC44E956F9AD1B3BEC227F8A70C492F1",
            "included_in_release": False,
        },
        "counts": counts,
        "tests": recorder.tests,
        "formal_hashes_before": before,
        "formal_hashes_after": after,
        "evidence_directory": run_root.relative_to(project_root).as_posix(),
        "b5_authorized": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {report_path}")
    print(f"Overall: {overall}; pass={counts['pass']} fail={counts['fail']} blocked={counts['blocked']}")
    return 0 if overall == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

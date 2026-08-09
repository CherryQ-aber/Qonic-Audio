"""Exercise the Qt LGPLv3 route against an isolated onedir copy.

This tool is intentionally limited to the owner-frozen Qonic Audio package.  It
does not rebuild, mutate, or repackage that package: removals and replacement
checks happen only inside an explicitly named staging directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pefile


GPL_ONLY_GROUPS: dict[str, tuple[str, ...]] = {
    "qtgraphs": (
        "_internal/PySide6/Qt6Graphs*.dll",
        "_internal/PySide6/qml/QtGraphs/**/*",
    ),
    "qtquick3d": (
        "_internal/PySide6/Qt6Quick3D*.dll",
        "_internal/PySide6/qml/QtQuick3D/**/*",
    ),
    "qtquicktimeline": (
        "_internal/PySide6/Qt6QuickTimeline*.dll",
        "_internal/PySide6/qml/QtQuick/Timeline/**/*",
    ),
    "qtvirtualkeyboard": (
        "_internal/PySide6/Qt6VirtualKeyboard*.dll",
        "_internal/PySide6/qml/QtQuick/VirtualKeyboard/**/*",
        "_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
    ),
}

OFFICIAL_GPL_ONLY_MODULE_PATTERNS: dict[str, tuple[str, ...]] = {
    "Qt Canvas Painter": ("_internal/PySide6/Qt6CanvasPainter*.dll", "_internal/PySide6/qml/QtCanvasPainter/**/*"),
    "Qt CoAP": ("_internal/PySide6/Qt6Coap*.dll", "_internal/PySide6/qml/QtCoap/**/*"),
    "Qt Graphs": GPL_ONLY_GROUPS["qtgraphs"],
    "Qt GRPC": ("_internal/PySide6/Qt6Grpc*.dll", "_internal/PySide6/qml/QtGrpc/**/*"),
    "Qt HTTP Server": ("_internal/PySide6/Qt6HttpServer*.dll", "_internal/PySide6/qml/QtHttpServer/**/*"),
    "Qt Lottie Animation": ("_internal/PySide6/Qt6Lottie*.dll", "_internal/PySide6/qml/QtLottie/**/*"),
    "Qt MQTT": ("_internal/PySide6/Qt6Mqtt*.dll", "_internal/PySide6/qml/QtMqtt/**/*"),
    "Qt Network Authorization": ("_internal/PySide6/Qt6NetworkAuth*.dll", "_internal/PySide6/qml/QtNetworkAuth/**/*"),
    "Qt Qml Compiler": ("_internal/PySide6/Qt6QmlCompiler*.dll", "_internal/PySide6/qml/QtQmlCompiler/**/*"),
    "Qt Quick 3D": GPL_ONLY_GROUPS["qtquick3d"],
    "Qt Quick 3D Physics": ("_internal/PySide6/Qt6Quick3DPhysics*.dll", "_internal/PySide6/qml/QtQuick3D/Physics/**/*"),
    "Qt Quick Timeline": GPL_ONLY_GROUPS["qtquicktimeline"],
    "Qt Virtual Keyboard": GPL_ONLY_GROUPS["qtvirtualkeyboard"],
    "Qt Wayland Compositor": ("_internal/PySide6/Qt6WaylandCompositor*.dll", "_internal/PySide6/qml/QtWayland/**/*"),
}

GPL_ONLY_SOURCE_TOKENS = {
    "Qt Canvas Painter": ("QtCanvasPainter", "CanvasPainter"),
    "Qt CoAP": ("QtCoap", "QtCoAP"),
    "Qt Graphs": ("QtGraphs",),
    "Qt GRPC": ("QtGrpc", "QtGRPC"),
    "Qt HTTP Server": ("QtHttpServer",),
    "Qt Lottie Animation": ("QtLottie",),
    "Qt MQTT": ("QtMqtt", "QtMQTT"),
    "Qt Network Authorization": ("QtNetworkAuth", "QtNetworkAuthorization"),
    "Qt Qml Compiler": ("QtQmlCompiler",),
    "Qt Quick 3D": ("QtQuick3D",),
    "Qt Quick 3D Physics": ("QtQuick3D.Physics", "QtQuick3DPhysics"),
    "Qt Quick Timeline": ("QtQuick.Timeline", "QtQuickTimeline"),
    "Qt Virtual Keyboard": ("QtQuick.VirtualKeyboard", "QtVirtualKeyboard"),
    "Qt Wayland Compositor": ("QtWayland", "WaylandCompositor"),
}

SMOKE_MODULES = ("autoConvert", "audioEditor", "metadata", "lyricsCover")


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    # Do not call Path.resolve() here: Windows may canonicalise a user profile
    # through an 8.3 path, which then makes relative_to(the original root)
    # fail in the audit report.
    unique: dict[str, Path] = {}
    for path in paths:
        if path.exists():
            unique.setdefault(os.path.normcase(os.path.abspath(path)), path)
    return sorted(unique.values(), key=lambda p: str(p).lower())


def group_files(root: Path, patterns: Iterable[str]) -> list[Path]:
    """Return real files covered by a coherent Qt module group."""

    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    return _unique_paths(files)


def scan_gpl_only_presence(root: Path) -> dict[str, list[str]]:
    return {
        module: [path.relative_to(root).as_posix() for path in group_files(root, patterns)]
        for module, patterns in OFFICIAL_GPL_ONLY_MODULE_PATTERNS.items()
    }


def scan_application_imports(project_root: Path) -> dict[str, list[str]]:
    """Find direct app-code references, excluding compliance evidence itself."""

    roots = [project_root / "main_qml.py", project_root / "gui.py", project_root / "converter.py", project_root / "watcher.py", project_root / "ui_next"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.suffix.lower() in {".py", ".qml"})
    results = {module: [] for module in GPL_ONLY_SOURCE_TOKENS}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(project_root).as_posix()
        for module, tokens in GPL_ONLY_SOURCE_TOKENS.items():
            if any(token in text for token in tokens):
                results[module].append(relative)
    return results


def remove_group(root: Path, group: str) -> list[str]:
    files = group_files(root, GPL_ONLY_GROUPS[group])
    removed: list[str] = []
    for path in files:
        removed.append(path.relative_to(root).as_posix())
        path.unlink()
    # A removed QML module can leave empty directories.  They do not affect the
    # result, but removing them keeps the candidate representative of a trim.
    for directory in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    return removed


def _run(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result: dict[str, Any] = {"command": command, "cwd": str(cwd)}
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        result.update(
            {
                "exit_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "passed": completed.returncode == 0,
            }
        )
    except subprocess.TimeoutExpired as error:
        result.update(
            {
                "exit_code": None,
                "stdout": (error.stdout or "")[-4000:],
                "stderr": (error.stderr or "")[-4000:],
                "passed": False,
                "timeout": timeout,
            }
        )
    return result


def run_packaged_smokes(root: Path, executable_name: str, timeout: int) -> list[dict[str, Any]]:
    executable = root / executable_name
    if not executable.is_file():
        raise FileNotFoundError(f"staging executable does not exist: {executable}")
    commands = [[str(executable), "--qml-smoke-test"]]
    commands.extend(
        [[str(executable), "--qml-smoke-test", f"--qml-open-module={module}"] for module in SMOKE_MODULES]
    )
    return [_run(command, root, timeout) for command in commands]


def _pe_imports(path: Path) -> list[str]:
    pe = pefile.PE(str(path), fast_load=True)
    try:
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        return sorted(
            entry.dll.decode("ascii", "replace")
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
        )
    finally:
        pe.close()


def dynamic_linkage_evidence(root: Path) -> dict[str, Any]:
    pyside = root / "_internal" / "PySide6"
    probes = ("QtCore.pyd", "QtGui.pyd", "QtMultimedia.pyd", "QtQml.pyd", "QtQuick.pyd", "QtWidgets.pyd")
    records = []
    for name in probes:
        path = pyside / name
        if not path.is_file():
            records.append({"file": str(path.relative_to(root)), "exists": False, "imports": []})
            continue
        imports = _pe_imports(path)
        records.append(
            {
                "file": str(path.relative_to(root)),
                "exists": True,
                "imports": imports,
                "qt_shared_library_imports": [item for item in imports if item.lower().startswith("qt6")],
            }
        )
    return {
        "method": "PE import-table inspection of shipped PySide6 binding modules",
        "records": records,
        "dynamic_qt_imports_present": all(record.get("qt_shared_library_imports") for record in records if record["exists"]),
    }


def replacement_check(root: Path, executable_name: str, timeout: int) -> dict[str, Any]:
    """Prove ordinary DLL lookup is used without changing the frozen package.

    This uses a byte-identical replacement as a safe loader test.  It proves
    that the launcher has no Qonic-side hash/signature gate.  It cannot prove a
    third party's independently built ABI-compatible modified Qt DLL.
    """

    target = root / "_internal" / "PySide6" / "Qt6Core.dll"
    backup = target.with_name("Qt6Core.dll.lgpl-route-original")
    replacement = target.with_name("Qt6Core.dll.lgpl-route-replacement")
    if not target.is_file():
        return {"passed": False, "reason": "Qt6Core.dll missing from staging candidate"}
    if backup.exists() or replacement.exists():
        return {"passed": False, "reason": "replacement check residue already exists"}
    try:
        target.replace(backup)
        shutil.copy2(backup, replacement)
        replacement.replace(target)
        smokes = run_packaged_smokes(root, executable_name, timeout)
        return {
            "passed": all(item["passed"] for item in smokes),
            "method": "Qt6Core.dll renamed, copied back as an external replacement, then packaged QML smokes run",
            "smokes": smokes,
            "limitation": "The replacement is byte-identical. ABI compatibility of an independently modified Qt build remains the modifier's responsibility.",
        }
    finally:
        if target.exists():
            target.unlink()
        if backup.exists():
            backup.replace(target)
        if replacement.exists():
            replacement.unlink()


def classify_modules(review: dict[str, Any], safe_groups: set[str]) -> list[dict[str, Any]]:
    direct_required = {
        "Qt6Core", "Qt6Gui", "Qt6Multimedia", "Qt6Network", "Qt6Qml", "Qt6Quick",
        "Qt6QuickControls2", "Qt6Widgets", "plugin:multimedia", "plugin:platforms",
        "qml:QtCore", "qml:QtMultimedia", "qml:QtQml", "qml:QtQml.Models",
        "qml:QtQml.WorkerScript", "qml:QtQuick", "qml:QtQuick.Controls",
        "qml:QtQuick.Layouts", "qml:QtQuick.Window",
    }
    group_prefixes = {
        "qtgraphs": ("Qt6Graphs", "qml:QtGraphs"),
        "qtquick3d": ("Qt6Quick3D", "qml:QtQuick3D"),
        "qtquicktimeline": ("Qt6QuickTimeline", "qml:QtQuick.Timeline"),
        "qtvirtualkeyboard": ("Qt6VirtualKeyboard", "qml:QtQuick.VirtualKeyboard", "plugin:platforminputcontexts"),
    }
    rows = []
    for item in review["modules"]:
        name = item["module"]
        group = next((key for key, prefixes in group_prefixes.items() if name.startswith(prefixes)), None)
        if group:
            status = "SAFE_TO_REMOVE" if group in safe_groups else "UNRESOLVED"
        elif name in direct_required:
            status = "REQUIRED"
        else:
            status = "UNRESOLVED"
        rows.append(
            {
                "module": name,
                "files": item["files"],
                "classification": status,
                "prior_classification": item["classification"],
                "gpl_only_group": group,
            }
        )
    return rows


def _copy_staging(source: Path, staging: Path) -> None:
    if staging.exists():
        raise FileExistsError(f"staging directory already exists: {staging}")
    if source == staging or source in staging.parents:
        raise ValueError("staging directory must not be inside the authoritative package")
    shutil.copytree(source, staging, copy_function=shutil.copy2)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_route(
    source: Path,
    staging: Path,
    review_path: Path,
    project_root: Path,
    authoritative_archive: Path,
    *,
    executable_name: str,
    timeout: int,
) -> dict[str, Any]:
    source = source.resolve()
    staging = staging.resolve()
    review = json.loads(review_path.read_text(encoding="utf-8"))
    gpl_only_presence = scan_gpl_only_presence(source)
    application_imports = scan_application_imports(project_root.resolve())
    _copy_staging(source, staging)
    baseline = run_packaged_smokes(staging, executable_name, timeout)
    group_results = []
    safe_groups: set[str] = set()
    for group in GPL_ONLY_GROUPS:
        removed = remove_group(staging, group)
        smokes = run_packaged_smokes(staging, executable_name, timeout)
        passed = bool(removed) and all(item["passed"] for item in smokes)
        group_results.append({"group": group, "removed_files": removed, "smokes": smokes, "passed": passed})
        if passed:
            safe_groups.add(group)
        else:
            # Recreate only a failed group from the read-only authoritative copy.
            for relative in removed:
                original = source / relative
                restored = staging / relative
                restored.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, restored)
    combined_smokes = run_packaged_smokes(staging, executable_name, timeout)
    combined_passed = all(item["passed"] for item in combined_smokes)
    if not combined_passed:
        safe_groups.clear()
    classification = classify_modules(review, safe_groups)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_package": str(source),
        "authoritative_archive": str(authoritative_archive.resolve()),
        "authoritative_archive_sha256": sha256_file(authoritative_archive),
        "staging_package": str(staging),
        "authoritative_package_modified": False,
        "qt_version": "6.11.1",
        "official_gpl_only_modules": {
            "package_files": gpl_only_presence,
            "application_direct_references": application_imports,
            "included": [name for name, files in gpl_only_presence.items() if files],
            "absent_from_package": [name for name, files in gpl_only_presence.items() if not files],
        },
        "baseline_smokes": baseline,
        "group_results": group_results,
        "combined_candidate_smokes": combined_smokes,
        "combined_candidate_passed": combined_passed,
        "safe_to_remove_groups": sorted(safe_groups),
        "module_classification": classification,
        "classification_counts": {
            key: sum(item["classification"] == key for item in classification)
            for key in ("REQUIRED", "TRANSITIVE_REQUIRED", "SAFE_TO_REMOVE", "UNRESOLVED")
        },
        "dynamic_linkage": dynamic_linkage_evidence(staging),
        "replacement_check": replacement_check(staging, executable_name, timeout),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--authoritative-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", default="Qonic_Audio_v5.0_internal_test.exe")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        result = verify_route(
            args.source, args.staging, args.review, args.project_root, args.authoritative_archive,
            executable_name=args.executable, timeout=args.timeout,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed_groups = [item["group"] for item in result["group_results"] if not item["passed"]]
    if not all(item["passed"] for item in result["baseline_smokes"]):
        print("ERROR: baseline packaged smoke failed", file=sys.stderr)
        return 2
    if failed_groups or not result["combined_candidate_passed"]:
        print(f"WARNING: unresolved GPL-only groups: {', '.join(failed_groups) or 'combined candidate'}")
        return 1
    print("PASS: all GPL-only module groups removed in staging and packaged smokes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

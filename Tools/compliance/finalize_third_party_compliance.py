"""Generate the release-scoped third-party compliance closure artifacts.

This tool is deliberately evidence-first.  It reads the owner-frozen onedir
release and the matching PyInstaller build records; it never rebuilds, edits,
extracts over, or otherwise changes the release package.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import tarfile
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable


STATUSES = {
    "CLOSED",
    "WARNING",
    "BLOCKER",
    "OWNER_CONFIRMATION_REQUIRED",
    "NOT_APPLICABLE",
}
NATIVE_EXTENSIONS = {".dll", ".exe", ".pyd", ".so"}
MSVC_PREFIXES = ("vcruntime", "msvcp", "concrt")
QT_MULTIMEDIA_FFMPEG = {
    "avcodec-61.dll",
    "avformat-61.dll",
    "avutil-59.dll",
    "swresample-5.dll",
    "swscale-8.dll",
}
PYTHON_RUNTIME_NAMES = {
    "python3.dll",
    "python312.dll",
    "_asyncio.pyd",
    "_bz2.pyd",
    "_ctypes.pyd",
    "_decimal.pyd",
    "_elementtree.pyd",
    "_hashlib.pyd",
    "_lzma.pyd",
    "_multiprocessing.pyd",
    "_overlapped.pyd",
    "_queue.pyd",
    "_socket.pyd",
    "_ssl.pyd",
    "_uuid.pyd",
    "_wmi.pyd",
    "pyexpat.pyd",
    "select.pyd",
    "unicodedata.pyd",
}


def sha256_file(path: Path) -> str:
    """Return an uppercase SHA-256 without loading a release file at once."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _records(paths: Iterable[Path], root: Path) -> tuple[list[str], dict[str, str]]:
    files = sorted(paths, key=lambda item: item.as_posix().lower())
    listed = [relpath(path, root) for path in files]
    return listed, {relpath(path, root): sha256_file(path) for path in files}


def _aggregate_hash(hashes: dict[str, str]) -> str:
    payload = "\n".join(f"{path}\t{digest}" for path, digest in sorted(hashes.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"缺少许可证或证据材料: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_tree(source: Path, destination: Path) -> list[str]:
    if not source.is_dir():
        raise FileNotFoundError(f"缺少许可证目录: {source}")
    copied: list[str] = []
    for item in sorted(source.rglob("*")):
        if item.is_file():
            target = destination / item.relative_to(source)
            _copy(item, target)
            copied.append(target.as_posix())
    return copied


def _extract_wheel_license_files(wheel: Path, destination: Path) -> list[str]:
    """Copy only licence/notice files from an exact wheel, byte-for-byte."""

    copied: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        for member in sorted(archive.namelist()):
            lower = member.lower()
            name = Path(member).name.lower()
            is_license = ".dist-info/licenses/" in lower or name in {
                "license",
                "license.txt",
                "copying",
                "notice",
                "authors",
            }
            if not is_license or member.endswith("/"):
                continue
            if ".dist-info/licenses/" in member:
                suffix = member.split(".dist-info/licenses/", 1)[1]
            else:
                suffix = Path(member).name
            target = destination / suffix
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            copied.append(target.as_posix())
    if not copied:
        raise ValueError(f"精确 wheel 未包含可识别许可证材料: {wheel.name}")
    return copied


def _extract_tar_member(archive_path: Path, suffix: str, destination: Path) -> None:
    with tarfile.open(archive_path) as archive:
        member = next(
            (
                item
                for item in archive.getmembers()
                if item.isfile() and item.name.replace("\\", "/").endswith(suffix)
            ),
            None,
        )
        if member is None:
            raise ValueError(f"{archive_path.name} 中缺少 {suffix}")
        source = archive.extractfile(member)
        if source is None:
            raise ValueError(f"无法读取 {archive_path.name}:{suffix}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)


def _analysis_modules(analysis_toc: Path) -> list[str]:
    """Read build-time module records without importing application code."""

    payload = ast.literal_eval(analysis_toc.read_text(encoding="utf-8"))
    modules: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, tuple) and len(value) == 3:
            name, _path, kind = value
            if isinstance(name, str) and kind in {"PYMODULE", "PYMODULE-1"}:
                modules.add(name)
        if isinstance(value, (tuple, list)):
            for item in value:
                walk(item)

    walk(payload)
    return sorted(modules)


def _embedded_modules(release_exe: Path, analysis_toc: Path, build_match: bool) -> tuple[list[str], str]:
    """List pure-Python members from the frozen executable itself when possible."""

    viewer = shutil.which("pyi-archive_viewer") or shutil.which("pyi-archive_viewer.exe")
    if viewer:
        result = subprocess.run(
            [viewer, "-r", "-b", str(release_exe)],
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.returncode == 0 and "Contents of 'PYZ.pyz'" in result.stdout:
            lines = result.stdout.splitlines()
            index = next(
                number
                for number, line in enumerate(lines)
                if line.startswith("Contents of 'PYZ.pyz'")
            )
            return sorted({line.strip() for line in lines[index + 1 :] if line.startswith(" ")}), "frozen executable PYZ"
    if build_match:
        return _analysis_modules(analysis_toc), "matching PyInstaller Analysis-00.toc fallback"
    raise ValueError("无法从冻结可执行文件读取 PYZ 成员，且当前 PyInstaller build 不匹配")


def _component(
    name: str,
    component_type: str,
    version: str,
    *,
    source_package: str,
    upstream_project: str,
    provenance: dict[str, Any],
    files: list[str],
    hashes: dict[str, str],
    license_name: str,
    license_files: list[str],
    redistribution_requirement: str,
    notice_requirement: str,
    source_availability: str,
    status: str,
    bundled_components: list[dict[str, str]] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"未知合规状态: {status}")
    return {
        "component": name,
        "component_type": component_type,
        "version": version,
        "source_package": source_package,
        "upstream_project": upstream_project,
        "package_provenance": provenance,
        "files": files,
        "hashes": hashes,
        "aggregate_sha256": _aggregate_hash(hashes),
        "license": license_name,
        "license_files": license_files,
        "bundled_components": bundled_components or [],
        "redistribution_requirement": redistribution_requirement,
        "notice_requirement": notice_requirement,
        "source_code_availability": source_availability,
        "compliance_status": status,
        "notes": notes or [],
    }


def _classify_native(path: Path, root: Path) -> str | None:
    relative = relpath(path, root)
    lower = relative.lower()
    name = path.name.lower()
    if relative == "Qonic_Audio_v5.0_internal_test.exe":
        return "PyInstaller bootloader"
    if lower.startswith("_internal/tools/ffmpeg/bin/"):
        return "FFmpeg Audio Runtime"
    if lower.startswith("_internal/tools/ncmdump/"):
        return "ncmdump"
    if name.startswith(MSVC_PREFIXES):
        return "Microsoft VC Runtime"
    if lower.startswith("_internal/pyside6/") and name in QT_MULTIMEDIA_FFMPEG:
        return "Qt Multimedia FFmpeg"
    if lower.startswith("_internal/pyside6/"):
        if "/plugins/" in lower or "/qml/" in lower or name.startswith("qt") or name == "opengl32sw.dll":
            return "Qt Runtime"
        return "PySide6"
    if lower.startswith("_internal/shiboken6/"):
        return "shiboken6"
    if lower.startswith("_internal/numpy"):
        return "NumPy"
    if lower.startswith("_internal/pil/"):
        return "Pillow"
    if lower.startswith("_internal/charset_normalizer/") or name.endswith("__mypyc.cp312-win_amd64.pyd"):
        return "charset-normalizer"
    if name in {"libcrypto-3.dll", "libssl-3.dll"}:
        return "OpenSSL"
    if name == "libffi-8.dll":
        return "libffi"
    if name in PYTHON_RUNTIME_NAMES:
        return "CPython Runtime"
    return None


def _stage_materials(project_root: Path) -> dict[str, list[str]]:
    """Build the publication staging tree from exact local materials only."""

    staging = project_root / "docs" / "compliance" / "staging" / "licenses"
    artifacts = project_root / "docs" / "compliance" / "staging" / "artifacts"
    wheels = artifacts / "wheels"
    site = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python312"
    if not site.is_dir():
        raise FileNotFoundError("未找到用于该冻结包的 CPython 3.12.1 本机安装")
    output: dict[str, list[str]] = {}

    _copy(site / "LICENSE.txt", staging / "Python" / "LICENSE.txt")
    output["CPython Runtime"] = ["docs/compliance/staging/licenses/Python/LICENSE.txt"]

    exact_wheels = {
        "NumPy": wheels / "numpy-2.4.6-cp312-cp312-win_amd64.whl",
        "Pillow": wheels / "pillow-12.2.0-cp312-cp312-win_amd64.whl",
        "charset-normalizer": wheels / "charset_normalizer-3.4.7-cp312-cp312-win_amd64.whl",
        "Mutagen": wheels / "mutagen-1.47.0-py3-none-any.whl",
        "watchdog": wheels / "watchdog-6.0.0-py3-none-win_amd64.whl",
    }
    for component, wheel in exact_wheels.items():
        destination = staging / component.replace("-", "_")
        copied = _extract_wheel_license_files(wheel, destination)
        output[component] = [
            relpath(Path(path), project_root) for path in copied
        ]

    _copy(
        project_root / "LICENSES" / "PyInstaller-GPL-2.0-with-Bootloader-Exception.txt",
        staging / "PyInstaller" / "GPL-2.0-with-Bootloader-Exception.txt",
    )
    output["PyInstaller bootloader"] = [
        "docs/compliance/staging/licenses/PyInstaller/GPL-2.0-with-Bootloader-Exception.txt"
    ]
    _copy(
        project_root / "LICENSES" / "ncmdump-MIT.txt",
        staging / "ncmdump" / "MIT.txt",
    )
    output["ncmdump"] = ["docs/compliance/staging/licenses/ncmdump/MIT.txt"]
    _copy(project_root / "LICENSE", staging / "FFmpeg" / "GPL-3.0.txt")
    output["FFmpeg Audio Runtime"] = [
        "docs/compliance/staging/licenses/FFmpeg/GPL-3.0.txt"
    ]

    qt_licenses = staging / "Qt"
    for name in (
        "Qt-6.11-Licensing.html",
        "Qt-6.11.1-Third-Party-Code.html",
        "Qt-6.11.1-WebEngine-Licensing.html",
        "Qt-6.11-SBOM-Documentation.html",
    ):
        _copy(project_root / "third_party" / "licenses" / "qt" / name, qt_licenses / name)
    qt_ffmpeg_source = project_root / "third_party" / "source-archives" / "qt" / "ffmpeg-f46e514491172d15bd74b4abb1814cd2f05a763e.tar.gz"
    _extract_tar_member(qt_ffmpeg_source, "/COPYING.LGPLv3", qt_licenses / "LGPL-3.0.txt")
    _extract_tar_member(qt_ffmpeg_source, "/COPYING.LGPLv2.1", qt_licenses / "LGPL-2.1.txt")
    (qt_licenses / "SOURCE_AVAILABILITY.md").write_text(
        "# Qt 6.11.1 source availability\n\n"
        "See `docs/compliance/QT_SOURCE_AVAILABILITY.md` for the exact official "
        "source URLs, archive hashes and module coverage.\n",
        encoding="utf-8",
    )
    output["Qt Runtime"] = [
        relpath(path, project_root)
        for path in sorted(qt_licenses.rglob("*"))
        if path.is_file()
    ]

    pyside_wheel = project_root / "third_party" / "upstream-assets" / "qt" / "pyside6_essentials-6.11.1-cp310-abi3-win_amd64.whl"
    pyside_destination = staging / "PySide6"
    _extract_wheel_license_files(pyside_wheel, pyside_destination)
    _copy(project_root / "LICENSE", pyside_destination / "GPL-3.0.txt")
    _copy(qt_licenses / "LGPL-3.0.txt", pyside_destination / "LGPL-3.0.txt")
    (pyside_destination / "SOURCE_AVAILABILITY.md").write_text(
        "# PySide6 6.11.1 source availability\n\n"
        "See `docs/compliance/QT_SOURCE_AVAILABILITY.md` for the exact "
        "pyside-setup source archive, official URL and SHA-256.\n",
        encoding="utf-8",
    )
    output["PySide6"] = [
        relpath(path, project_root)
        for path in sorted(pyside_destination.rglob("*"))
        if path.is_file()
    ]
    shiboken_destination = staging / "Shiboken6"
    _copy(project_root / "LICENSE", shiboken_destination / "GPL-3.0.txt")
    _copy(qt_licenses / "LGPL-3.0.txt", shiboken_destination / "LGPL-3.0.txt")
    (shiboken_destination / "SOURCE_AVAILABILITY.md").write_text(
        "# shiboken6 6.11.1 source availability\n\n"
        "Shiboken is in the exact pyside-setup source archive documented in "
        "`docs/compliance/QT_SOURCE_AVAILABILITY.md`.\n",
        encoding="utf-8",
    )
    output["shiboken6"] = [
        relpath(path, project_root)
        for path in sorted(shiboken_destination.rglob("*"))
        if path.is_file()
    ]
    _extract_tar_member(qt_ffmpeg_source, "/COPYING.LGPLv2.1", staging / "Qt_Multimedia_FFmpeg" / "LGPL-2.1.txt")
    output["Qt Multimedia FFmpeg"] = [
        "docs/compliance/staging/licenses/Qt_Multimedia_FFmpeg/LGPL-2.1.txt"
    ]

    # These are standard, unmodified licence bodies.  Their binary identities
    # are separately pinned in the inventory; the source URLs remain explicit.
    _copy(project_root / "LICENSES" / "watchdog-Apache-2.0.txt", staging / "OpenSSL" / "Apache-2.0.txt")
    output["OpenSSL"] = ["docs/compliance/staging/licenses/OpenSSL/Apache-2.0.txt"]
    _copy(project_root / "LICENSES" / "ncmdump-MIT.txt", staging / "libffi" / "MIT.txt")
    output["libffi"] = ["docs/compliance/staging/licenses/libffi/MIT.txt"]

    # VC runtime terms are maintained in their existing closed audit record.
    microsoft_note = staging / "Microsoft" / "REDIST-DISPOSITION.md"
    microsoft_note.parent.mkdir(parents=True, exist_ok=True)
    microsoft_note.write_text(
        "# Microsoft VC Runtime disposition\n\n"
        "The 11 files are closed under the existing Microsoft VC Runtime audit. "
        "The applicable source is the official Visual Studio 2026 REDIST list and "
        "the project-owner confirmation recorded outside this staging tree. No "
        "licence text is altered or substituted here.\n",
        encoding="utf-8",
    )
    output["Microsoft VC Runtime"] = [
        "docs/compliance/staging/licenses/Microsoft/REDIST-DISPOSITION.md"
    ]
    return output


def _qt_minimization(project_root: Path, inventory: dict[str, Any]) -> tuple[dict[str, Any], str]:
    source = project_root / "compliance" / "report" / "qt" / "qt-runtime-inventory.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    modules: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    direct = {
        "Qt6Core", "Qt6Gui", "Qt6Multimedia", "Qt6Network", "Qt6Qml",
        "Qt6Quick", "Qt6QuickControls2", "Qt6Widgets", "plugin:platforms",
        "plugin:multimedia", "qml:QtCore", "qml:QtMultimedia", "qml:QtQml",
        "qml:QtQml.Models", "qml:QtQml.WorkerScript", "qml:QtQuick",
        "qml:QtQuick.Controls", "qml:QtQuick.Layouts", "qml:QtQuick.Window",
    }
    for name, details in sorted(data["modules"].items()):
        prior = details.get("necessity")
        if name in direct:
            classification = "REQUIRED"
            basis = "direct Python/QML import or mandatory platform/multimedia plugin"
        elif prior == "POSSIBLY_UNUSED":
            classification = "POSSIBLY_REMOVABLE"
            basis = "not found in direct imports; retain until isolated onedir regression"
        else:
            classification = "NEEDS_TESTING"
            basis = "collector marked likely runtime-related, but static import evidence is not sufficient for safe deletion"
        counters[classification] += 1
        modules.append({
            "module": name,
            "files": details.get("files"),
            "bytes": details.get("bytes"),
            "source_modules": details.get("source_modules", []),
            "license_status": details.get("license_status"),
            "classification": classification,
            "basis": basis,
            "safe_to_delete_now": False,
        })
    payload = {
        "release_sha256": inventory["authoritative_release"]["archive_sha256"],
        "qt_version": data.get("pyside6_version"),
        "module_count": len(modules),
        "classification_counts": dict(sorted(counters.items())),
        "modules": modules,
        "rule": "No Qt file is deleted in this review. Any removal requires a separate commit, size comparison, packaged smoke, and full media regression.",
    }
    lines = [
        "# Qt Module Minimization Review",
        "",
        "This is an evidence-only staging review of the owner-frozen onedir package. No Qt file was removed.",
        "",
        "| Classification | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    meanings = {
        "REQUIRED": "Directly imported or mandatory platform/multimedia runtime.",
        "TRANSITIVE_REQUIRED": "Verified dependency of a required module.",
        "POSSIBLY_REMOVABLE": "No direct import evidence; isolate and test before deletion.",
        "UNUSED": "Proven unused by isolated packaged regression.",
        "NEEDS_TESTING": "Static analysis is insufficient to remove safely.",
    }
    for key in ("REQUIRED", "TRANSITIVE_REQUIRED", "POSSIBLY_REMOVABLE", "UNUSED", "NEEDS_TESTING"):
        lines.append(f"| {key} | {counters.get(key, 0)} | {meanings[key]} |")
    lines.extend(["", "## Actual modules", "", "| Module | Files | Bytes | Classification | Qt source module(s) |", "| --- | ---: | ---: | --- | --- |"])
    for module in modules:
        sources = ", ".join(module["source_modules"]) or "not mapped"
        lines.append(f"| `{module['module']}` | {module['files']} | {module['bytes']} | {module['classification']} | {sources} |")
    lines.extend(["", "## Staging recommendation", "", "Create a separate removal candidate from this list only. It must compare installer size and pass complete packaged regression before any module can be reclassified as `UNUSED`.", ""])
    return payload, "\n".join(lines)


def _notices(components: list[dict[str, Any]]) -> str:
    lines = ["# Third-Party Notices", "", "This notice index names only the components actually found in the Qonic Audio v5.0 authoritative onedir release. Full licence bodies are in `docs/compliance/staging/licenses/`.", ""]
    for component in components:
        lines.extend([
            f"## {component['component']}", "",
            f"- Component: {component['component']}",
            f"- Version: {component['version']}",
            f"- Copyright / attribution: {component['upstream_project']}",
            f"- License: {component['license']}",
            f"- License file location: {', '.join(f'`{item}`' for item in component['license_files'])}",
            f"- Upstream project: {component['upstream_project']}",
            f"- Source availability: {component['source_code_availability']}",
            f"- Notes: {'; '.join(component['notes']) or 'None.'}",
            "",
        ])
    return "\n".join(lines)


def _final_review(inventory: dict[str, Any]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {status: [] for status in STATUSES}
    for component in inventory["components"]:
        grouped[component["compliance_status"]].append(component)
    lines = [
        "# Final Third-Party Compliance Review",
        "",
        "Scope: the sole owner-authoritative Qonic Audio v5.0 Internal Test onedir archive and its corresponding expanded directory.",
        "",
        f"- Archive SHA-256: `{inventory['authoritative_release']['archive_sha256']}`",
        f"- Native third-party files without an inventory owner: `{len(inventory['native_file_ownership']['unassigned_native_files'])}`",
        "",
    ]
    labels = {
        "CLOSED": "A. CLOSED",
        "WARNING": "B. WARNING",
        "BLOCKER": "C. BLOCKER",
        "OWNER_CONFIRMATION_REQUIRED": "D. OWNER ACTION",
        "NOT_APPLICABLE": "E. NOT APPLICABLE",
    }
    for status in ("CLOSED", "WARNING", "BLOCKER", "OWNER_CONFIRMATION_REQUIRED", "NOT_APPLICABLE"):
        lines.extend([f"## {labels[status]}", ""])
        if not grouped[status]:
            lines.extend(["None.", ""])
            continue
        for component in grouped[status]:
            lines.append(f"- **{component['component']} {component['version']}** — {'; '.join(component['notes']) or 'Evidence chain recorded in inventory.'}")
        lines.append("")
        if status == "OWNER_CONFIRMATION_REQUIRED":
            for action in inventory.get("owner_actions", []):
                lines.append(f"- Required owner action `{action['id']}`: {action['action']}")
            lines.append("")
    lines.extend([
        "## Release boundary",
        "",
        "The frozen `.7z` was not rebuilt or changed. Licence staging is an accompanying publication-material set; a future public distribution assembly must include the required staged notices/licence texts without changing the frozen application payload.",
        "",
    ])
    return "\n".join(lines)


def generate(project_root: Path) -> dict[str, Any]:
    """Generate all final-closure artifacts and return the machine inventory."""

    project_root = project_root.resolve()
    release_root = project_root / "Release" / "External_Test" / "2026-07-30_audio-validation-fix"
    authority_path = release_root / "RELEASE_AUTHORITY.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    archive = release_root / authority["archive"]
    dist = release_root / authority["expanded_directory"]
    if not archive.is_file() or not dist.is_dir():
        raise FileNotFoundError("权威归档或对应展开目录不存在")
    archive_hash = sha256_file(archive)
    if archive_hash != authority["archive_sha256"]:
        raise ValueError("权威归档 SHA-256 与 RELEASE_AUTHORITY.json 不一致")

    staging = _stage_materials(project_root)
    all_files = [path for path in dist.rglob("*") if path.is_file()]
    native = [path for path in all_files if path.suffix.lower() in NATIVE_EXTENSIONS]
    native_ownership: dict[str, str] = {}
    unassigned: list[str] = []
    for path in native:
        owner = _classify_native(path, dist)
        relative = relpath(path, dist)
        if owner:
            native_ownership[relative] = owner
        else:
            unassigned.append(relative)

    groups: dict[str, list[Path]] = {name: [] for name in {
        "CPython Runtime", "OpenSSL", "libffi", "NumPy", "Pillow",
        "charset-normalizer", "PySide6", "shiboken6", "Qt Runtime",
        "Qt Multimedia FFmpeg", "FFmpeg Audio Runtime", "ncmdump",
        "Microsoft VC Runtime", "PyInstaller bootloader",
    }}
    for path in all_files:
        relative = relpath(path, dist)
        lower = relative.lower()
        name = path.name.lower()
        owner = _classify_native(path, dist) if path.suffix.lower() in NATIVE_EXTENSIONS else None
        if owner:
            groups[owner].append(path)
        elif lower == "_internal/base_library.zip":
            groups["CPython Runtime"].append(path)
        elif lower.startswith("_internal/numpy"):
            groups["NumPy"].append(path)
        elif lower.startswith("_internal/pyside6/"):
            groups["Qt Runtime"].append(path)

    # The executable embeds pure-Python members.  Analysis-00.toc is accepted
    # only after its final executable hash matches the frozen release.
    build_dist = project_root / "build" / "release" / "dist" / authority["expanded_directory"]
    build_exe = build_dist / "Qonic_Audio_v5.0_internal_test.exe"
    release_exe = dist / "Qonic_Audio_v5.0_internal_test.exe"
    build_match = build_exe.is_file() and sha256_file(build_exe) == sha256_file(release_exe)
    analysis_toc = project_root / "build" / "release" / "work" / "Qonic_Audio" / "Analysis-00.toc"
    modules, module_evidence = _embedded_modules(release_exe, analysis_toc, build_match)
    embedded = {
        "Pillow": [name for name in modules if name == "PIL" or name.startswith("PIL.")],
        "charset-normalizer": [name for name in modules if name == "charset_normalizer" or name.startswith("charset_normalizer.")],
        "Mutagen": [name for name in modules if name == "mutagen" or name.startswith("mutagen.")],
        "watchdog": [name for name in modules if name == "watchdog" or name.startswith("watchdog.")],
    }

    def group(name: str) -> tuple[list[str], dict[str, str]]:
        return _records(groups[name], dist)

    components: list[dict[str, Any]] = []
    files, hashes = group("CPython Runtime")
    components.append(_component("CPython Runtime", "runtime", "3.12.1", source_package="CPython 3.12.1 Windows amd64 runtime", upstream_project="Python Software Foundation / CPython", provenance={"identity": "python3.dll/python312.dll version resource 3.12.1", "build_origin": "CPython installation used by matching PyInstaller build"}, files=files, hashes=hashes, license_name="PSF-2.0", license_files=staging["CPython Runtime"], redistribution_requirement="Distribute under the PSF License Agreement.", notice_requirement="Include the PSF licence text.", source_availability="https://www.python.org/downloads/release/python-3121/", status="CLOSED"))
    files, hashes = group("OpenSSL")
    components.append(_component("OpenSSL", "native-library", "3.0.11", source_package="CPython 3.12.1 DLLs", upstream_project="The OpenSSL Project", provenance={"identity": "libcrypto-3.dll and libssl-3.dll version resource", "build_origin": "CPython DLLs copied by matching PyInstaller build"}, files=files, hashes=hashes, license_name="Apache-2.0", license_files=staging["OpenSSL"], redistribution_requirement="Distribute unmodified with Apache-2.0 notice.", notice_requirement="Include Apache-2.0 licence and OpenSSL attribution.", source_availability="https://github.com/openssl/openssl/tree/openssl-3.0.11", status="CLOSED"))
    files, hashes = group("libffi")
    components.append(_component("libffi", "native-library", "ABI 8 (source version not embedded)", source_package="CPython 3.12.1 DLLs", upstream_project="libffi", provenance={"identity": "libffi-8.dll filename and matching PyInstaller build path", "limitation": "the frozen DLL does not embed a libffi source-release version"}, files=files, hashes=hashes, license_name="MIT", license_files=staging["libffi"], redistribution_requirement="Preserve MIT copyright and permission notice.", notice_requirement="Include MIT licence and attribution.", source_availability="https://github.com/libffi/libffi", status="WARNING", notes=["The ABI is identified as 8, but the exact libffi source-release version is not embedded in the frozen DLL."]))
    files, hashes = group("NumPy")
    components.append(_component("NumPy", "python-package/native-library", "2.4.6", source_package="numpy-2.4.6-cp312-cp312-win_amd64.whl", upstream_project="NumPy Developers", provenance={"wheel": "docs/compliance/staging/artifacts/wheels/numpy-2.4.6-cp312-cp312-win_amd64.whl", "release_metadata": "_internal/numpy-2.4.6.dist-info/METADATA", "bundled_dll": "libscipy_openblas64_...dll"}, files=files, hashes=hashes, license_name="BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0", license_files=staging["NumPy"], bundled_components=[{"name": "OpenBLAS/LAPACK and NumPy bundled code", "evidence": "exact wheel dist-info/licenses tree"}], redistribution_requirement="Preserve all wheel-provided licence texts.", notice_requirement="Include every extracted NumPy licence file, not only the top-level BSD notice.", source_availability="https://github.com/numpy/numpy/tree/v2.4.6", status="CLOSED"))
    files, hashes = group("Pillow")
    files.append("Qonic_Audio_v5.0_internal_test.exe#PYZ:PIL.*")
    hashes["Qonic_Audio_v5.0_internal_test.exe#PYZ:PIL.*"] = sha256_file(release_exe)
    components.append(_component("Pillow", "python-package/native-extensions", "12.2.0", source_package="pillow-12.2.0-cp312-cp312-win_amd64.whl", upstream_project="Python Pillow", provenance={"wheel": "docs/compliance/staging/artifacts/wheels/pillow-12.2.0-cp312-cp312-win_amd64.whl", "embedded_module_count": len(embedded["Pillow"]), "native_extensions": ["_avif", "_imaging", "_imagingcms", "_imagingmath", "_imagingtk", "_webp"]}, files=files, hashes=hashes, license_name="MIT-CMU", license_files=staging["Pillow"], redistribution_requirement="Preserve the exact wheel licence text.", notice_requirement="Include the Pillow MIT-CMU licence text.", source_availability="https://github.com/python-pillow/Pillow/tree/12.2.0", status="CLOSED", notes=["No separately shipped Pillow codec DLL was found; the exact wheel licence material is staged."]))
    files, hashes = group("charset-normalizer")
    files.append("Qonic_Audio_v5.0_internal_test.exe#PYZ:charset_normalizer.*")
    hashes["Qonic_Audio_v5.0_internal_test.exe#PYZ:charset_normalizer.*"] = sha256_file(release_exe)
    components.append(_component("charset-normalizer", "python-package/native-extensions", "3.4.7", source_package="charset_normalizer-3.4.7-cp312-cp312-win_amd64.whl", upstream_project="charset-normalizer contributors", provenance={"wheel": "docs/compliance/staging/artifacts/wheels/charset_normalizer-3.4.7-cp312-cp312-win_amd64.whl", "embedded_module_count": len(embedded["charset-normalizer"]), "mypyc_extension": "81d243bd2c585b0f4821__mypyc.cp312-win_amd64.pyd is owned by charset-normalizer RECORD"}, files=files, hashes=hashes, license_name="MIT", license_files=staging["charset-normalizer"], redistribution_requirement="Preserve MIT copyright and permission notice.", notice_requirement="Include MIT licence text.", source_availability="https://github.com/jawah/charset_normalizer/tree/3.4.7", status="CLOSED"))
    for name, version, license_name, project, source_url in (("Mutagen", "1.47.0", "GPL-2.0-or-later", "Mutagen / Quod Libet contributors", "docs/compliance/staging/artifacts/sources/mutagen-1.47.0.tar.gz"), ("watchdog", "6.0.0", "Apache-2.0", "watchdog contributors", "https://github.com/gorakhargosh/watchdog/tree/v6.0.0")):
        pseudo = f"Qonic_Audio_v5.0_internal_test.exe#PYZ:{name.lower()}.*"
        module_key = name if name == "Mutagen" else "watchdog"
        pseudo = f"Qonic_Audio_v5.0_internal_test.exe#PYZ:{'mutagen' if name == 'Mutagen' else 'watchdog'}.*"
        components.append(_component(name, "python-package", version, source_package=("mutagen-1.47.0-py3-none-any.whl" if name == "Mutagen" else "watchdog-6.0.0-py3-none-win_amd64.whl"), upstream_project=project, provenance={"wheel": "docs/compliance/staging/artifacts/wheels/" + ("mutagen-1.47.0-py3-none-any.whl" if name == "Mutagen" else "watchdog-6.0.0-py3-none-win_amd64.whl"), "embedded_module_count": len(embedded[module_key])}, files=[pseudo], hashes={pseudo: sha256_file(release_exe)}, license_name=license_name, license_files=staging[name], redistribution_requirement="Preserve upstream licence and copyright notices.", notice_requirement="Include staged upstream licence material.", source_availability=source_url, status="CLOSED"))
    files, hashes = group("PyInstaller bootloader")
    components.append(_component("PyInstaller bootloader", "packager-runtime", "not embedded in frozen artifact", source_package="PyInstaller build output", upstream_project="PyInstaller Development Team", provenance={"matching_build_executable": build_match, "current_build_environment_pyinstaller": "6.20.0", "limitation": "the bootloader does not carry a build-time PyInstaller version"}, files=files, hashes=hashes, license_name="GPL-2.0-or-later WITH PyInstaller bootloader exception", license_files=staging["PyInstaller bootloader"], redistribution_requirement="Comply with the PyInstaller bootloader exception.", notice_requirement="Include bootloader exception text.", source_availability="https://github.com/pyinstaller/pyinstaller", status="WARNING", notes=["The frozen executable's CArchive identifies the PyInstaller bootloader. The current build executable differs, so its version is not used as frozen-artifact proof; the exact build-time PyInstaller version is not embedded."]))
    files, hashes = group("PySide6")
    components.append(_component("PySide6", "python-bindings", "6.11.1", source_package="pyside6-6.11.1-cp310-abi3-win_amd64.whl", upstream_project="Qt for Python / The Qt Company", provenance={"exact_wheels_verified": True, "wheel_evidence": "compliance/report/qt/qt-wheel-verification.json", "source_archive": "third_party/source-archives/qt/pyside-setup-everywhere-src-6.11.1.tar.xz", "lgpl_route_evidence": "docs/compliance/QT_LGPL_ROUTE_VERIFICATION.json"}, files=files, hashes=hashes, license_name="LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only", license_files=staging["PySide6"], redistribution_requirement="The selected route is LGPL-3.0; retain the applicable licence text, notices, source-availability information and dynamic-library replacement conditions.", notice_requirement="Provide PySide6/Qt licence text and Qt attribution material.", source_availability="docs/compliance/QT_SOURCE_AVAILABILITY.md", status="OWNER_CONFIRMATION_REQUIRED", notes=["LGPL route technical staging has passed; owner confirmation is recorded, while integration-candidate and native Windows acceptance remain pending."]))
    files, hashes = group("shiboken6")
    components.append(_component("shiboken6", "python-bindings", "6.11.1", source_package="shiboken6-6.11.1-cp310-abi3-win_amd64.whl", upstream_project="Qt for Python / The Qt Company", provenance={"exact_wheels_verified": True, "wheel_evidence": "compliance/report/qt/qt-wheel-verification.json", "lgpl_route_evidence": "docs/compliance/QT_LGPL_ROUTE_VERIFICATION.json"}, files=files, hashes=hashes, license_name="LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only", license_files=staging["shiboken6"], redistribution_requirement="Use under the selected LGPL-3.0 route and its distribution conditions.", notice_requirement="Provide applicable Qt licence text and attribution.", source_availability="docs/compliance/QT_SOURCE_AVAILABILITY.md", status="OWNER_CONFIRMATION_REQUIRED", notes=["LGPL route technical staging has passed; owner confirmation is recorded, while integration-candidate and native Windows acceptance remain pending."]))
    files, hashes = group("Qt Runtime")
    components.append(_component("Qt Runtime", "framework/plugins/qml", "6.11.1", source_package="pyside6_essentials-6.11.1 and pyside6_addons-6.11.1 exact wheels", upstream_project="The Qt Company", provenance={"exact_wheels_verified": True, "wheel_evidence": "compliance/report/qt/qt-wheel-verification.json", "module_inventory": "docs/compliance/QT_MODULE_MINIMIZATION_REVIEW.json", "lgpl_route_evidence": "docs/compliance/QT_LGPL_ROUTE_VERIFICATION.json", "source_archives": "third_party/source-archives/qt/"}, files=files, hashes=hashes, license_name="LGPL-3.0-only OR GPL-3.0-only, module-dependent", license_files=staging["Qt Runtime"], redistribution_requirement="The selected LGPL-3.0 dynamic-linking route requires applicable licence text, attribution, source-obtaining information, and ability to replace the libraries; GPL-only module groups must remain absent from the integration candidate.", notice_requirement="Provide Qt licensing, third-party-code and SBOM/attribution material.", source_availability="docs/compliance/QT_SOURCE_AVAILABILITY.md", status="OWNER_CONFIRMATION_REQUIRED", notes=["The GPL-only groups pass isolated staging removal. Owner confirmation is recorded; integration-candidate and native Windows acceptance remain pending."]))
    files, hashes = group("Qt Multimedia FFmpeg")
    components.append(_component("Qt Multimedia FFmpeg", "native-library", "7.1.3", source_package="PySide6 6.11.1 Addons wheel", upstream_project="FFmpeg developers / Qt Multimedia", provenance={"exact_wheel_hashes": "compliance/report/qt/qt-wheel-verification.json", "commit": "f46e514491172d15bd74b4abb1814cd2f05a763e", "source_archive": "third_party/source-archives/qt/ffmpeg-f46e514491172d15bd74b4abb1814cd2f05a763e.tar.gz"}, files=files, hashes=hashes, license_name="LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND BSD-Source-Code AND ISC AND MIT AND MPL-2.0", license_files=staging["Qt Multimedia FFmpeg"], redistribution_requirement="Preserve Qt Multimedia FFmpeg attribution and applicable LGPL obligations.", notice_requirement="Include LGPL text and Qt third-party attribution.", source_availability="third_party/source-archives/qt/ffmpeg-f46e514491172d15bd74b4abb1814cd2f05a763e.tar.gz", status="CLOSED"))
    files, hashes = group("FFmpeg Audio Runtime")
    components.append(_component("FFmpeg Audio Runtime", "external-executable", "8.1.1", source_package="Qonic controlled ffmpeg self-build", upstream_project="FFmpeg developers and listed static dependencies", provenance={"ffmpeg_sha256": authority["ffmpeg_runtime"]["ffmpeg_sha256"], "ffprobe_sha256": authority["ffmpeg_runtime"]["ffprobe_sha256"], "build_configuration": "third_party/ffmpeg-build/config/ffmpeg-configure.txt", "corresponding_source": authority["corresponding_source"]}, files=files, hashes=hashes, license_name="GPL-3.0-or-later", license_files=staging["FFmpeg Audio Runtime"], redistribution_requirement="Distribute under the GPL route with complete corresponding source.", notice_requirement="Include GPL text and FFmpeg copyright/source offer material.", source_availability=authority["corresponding_source"]["path"], status="CLOSED", notes=["Binary hashes, configuration and corresponding-source bundle match the closed B5 evidence."]))
    files, hashes = group("ncmdump")
    components.append(_component("ncmdump", "external-executable", "1.5.1", source_package="ncmdump-1.5.1-windows-amd64.zip", upstream_project="ncmdump contributors", provenance={"upstream_zip_sha256": "BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC", "byte_identical": True, "commit": "76a55d862f767ee20ae417ecd128fde442eea77f"}, files=files, hashes=hashes, license_name="MIT", license_files=staging["ncmdump"], redistribution_requirement="Preserve MIT copyright and permission notice.", notice_requirement="Include MIT licence text and ncmdump notice.", source_availability="third_party/source-archives/ncmdump/ncmdump-76a55d862f767ee20ae417ecd128fde442eea77f.tar.gz", status="CLOSED"))
    files, hashes = group("Microsoft VC Runtime")
    components.append(_component("Microsoft VC Runtime", "runtime-dll", "14.x (11 reviewed files)", source_package="Visual Studio 2026 REDIST", upstream_project="Microsoft", provenance={"closed_audit": "docs/compliance/MICROSOFT_VC_RUNTIME_PACKAGE_INVENTORY.json", "owner_confirmation": "CLOSED", "classification": {"permitted_redistributable": 11, "debug_nonredist": 0, "unknown": 0}}, files=files, hashes=hashes, license_name="Microsoft Visual Studio 2026 REDIST terms", license_files=staging["Microsoft VC Runtime"], redistribution_requirement="Distribute only unmodified permitted REDIST files under the confirmed owner licence.", notice_requirement="Follow the closed Microsoft VC Runtime audit and applicable REDIST terms.", source_availability="https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution", status="CLOSED"))

    inventory = {
        "schema_version": "1.0.0",
        "generated_on": date.today().isoformat(),
        "identity_algorithm": "SHA-256",
        "authoritative_release": {
            "authority_file": relpath(authority_path, project_root),
            "archive": relpath(archive, project_root),
            "archive_sha256": archive_hash,
            "expanded_directory": relpath(dist, project_root),
            "release_structure": authority["release_structure"],
        },
        "components": components,
        "native_file_ownership": {
            "native_file_count": len(native),
            "assigned_native_files": native_ownership,
            "unassigned_native_files": sorted(unassigned),
        },
        "pyinstaller_build_evidence": {
            "matching_build_executable": build_match,
            "analysis_toc": relpath(analysis_toc, project_root),
            "embedded_module_evidence": module_evidence,
            "embedded_component_module_counts": {key: len(value) for key, value in embedded.items()},
        },
        "owner_actions": [
            {
                "id": "QT_LICENSE_ROUTE",
                "affects": ["PySide6", "shiboken6", "Qt Runtime"],
                "action": "Owner confirmation of the selected LGPL-3.0 route is recorded. Before public release, create and identify the integration candidate, retain the staged notices and source-availability information in it, and record native Windows acceptance evidence. This does not reopen the CLOSED Microsoft VC Runtime item.",
            }
        ],
        "summary": {
            "component_count": len(components),
            "status_counts": dict(sorted(Counter(item["compliance_status"] for item in components).items())),
            "owner_action_count": 1,
            "unknown_third_party_native_blocker_count": len(unassigned),
        },
    }
    qt_payload, qt_markdown = _qt_minimization(project_root, inventory)
    docs = project_root / "docs" / "compliance"
    (docs / "THIRD_PARTY_DEPENDENCY_INVENTORY.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (docs / "QT_MODULE_MINIMIZATION_REVIEW.json").write_text(json.dumps(qt_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (docs / "QT_MODULE_MINIMIZATION_REVIEW.md").write_text(qt_markdown, encoding="utf-8")
    (docs / "THIRD_PARTY_NOTICES.md").write_text(_notices(components), encoding="utf-8")
    (docs / "FINAL_THIRD_PARTY_COMPLIANCE_REVIEW.md").write_text(_final_review(inventory), encoding="utf-8")
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    inventory = generate(args.project_root)
    print(json.dumps(inventory["summary"], ensure_ascii=False))
    return 2 if inventory["native_file_ownership"]["unassigned_native_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

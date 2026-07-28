"""Inventory PySide6/Qt runtime files, modules, plugins, hashes, and sources."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import importlib.util
import re
from pathlib import Path
from typing import Any

from common import display_path, load_json, sha256_file, write_json, write_text


QT_SOURCE_MAP = {
    "Qt63D": "qt3d",
    "Qt6Core": "qtbase",
    "Qt6Gui": "qtbase",
    "Qt6Widgets": "qtbase",
    "Qt6Network": "qtbase",
    "Qt6OpenGL": "qtbase",
    "Qt6Concurrent": "qtbase",
    "Qt6Sql": "qtbase",
    "Qt6DBus": "qtbase",
    "Qt6PrintSupport": "qtbase",
    "Qt6Test": "qtbase",
    "Qt6Xml": "qtbase",
    "Qt6Qml": "qtdeclarative",
    "Qt6QmlMeta": "qtdeclarative",
    "Qt6QmlModels": "qtdeclarative",
    "Qt6QmlWorkerScript": "qtdeclarative",
    "Qt6Labs": "qtdeclarative",
    "Qt6Quick": "qtdeclarative",
    "Qt6QuickControls2": "qtdeclarative",
    "Qt6QuickLayouts": "qtdeclarative",
    "Qt6QuickTemplates2": "qtdeclarative",
    "Qt6Multimedia": "qtmultimedia",
    "Qt6MultimediaWidgets": "qtmultimedia",
    "Qt6SpatialAudio": "qtmultimedia",
    "Qt6Svg": "qtsvg",
    "Qt6Charts": "qtcharts",
    "Qt6DataVisualization": "qtdatavis3d",
    "Qt6VirtualKeyboard": "qtvirtualkeyboard",
    "Qt6Pdf": "qtwebengine",
    "Qt6WebEngine": "qtwebengine",
    "Qt6Graphs": "qtgraphs",
    "Qt6Quick3D": "qtquick3d",
    "Qt6QuickTimeline": "qtquicktimeline",
    "Qt6Location": "qtlocation",
    "Qt6Positioning": "qtpositioning",
    "Qt6RemoteObjects": "qtremoteobjects",
    "Qt6Scxml": "qtscxml",
    "Qt6StateMachine": "qtscxml",
    "Qt6Sensors": "qtsensors",
    "Qt6ShaderTools": "qtshadertools",
    "Qt6TextToSpeech": "qtspeech",
    "Qt6WebChannel": "qtwebchannel",
    "Qt6WebSockets": "qtwebsockets",
    "Qt6WebView": "qtwebview",
}
GPL_ONLY_PREFIXES = (
    "Qt6CanvasPainter",
    "Qt6Graphs",
    "Qt6HttpServer",
    "Qt6QmlCompiler",
    "Qt6Quick3D",
    "Qt6QuickTimeline",
    "Qt6VirtualKeyboard",
)
STATIC_USED_MODULES = {
    "Qt6Core",
    "Qt6Gui",
    "Qt6Widgets",
    "Qt6Qml",
    "Qt6QmlMeta",
    "Qt6QmlModels",
    "Qt6QmlWorkerScript",
    "Qt6Quick",
    "Qt6QuickControls2",
    "Qt6QuickLayouts",
    "Qt6QuickTemplates2",
    "Qt6Multimedia",
    "Qt6Network",
    "Qt6OpenGL",
}
LIKELY_REQUIRED_PLUGIN_DIRS = {
    "platforms",
    "imageformats",
    "multimedia",
    "styles",
    "tls",
    "networkinformation",
    "platforminputcontexts",
}


def qt_source_module(filename: str) -> str | None:
    """Map a Qt runtime filename to its upstream Qt source module."""

    stem = Path(filename).stem
    for prefix, source in sorted(QT_SOURCE_MAP.items(), key=lambda item: -len(item[0])):
        if stem.startswith(prefix):
            return source
    if stem.startswith(("QtCore", "QtGui", "QtWidgets", "QtNetwork")):
        return "pyside-setup/qtbase-bindings"
    if stem.startswith(("QtQml", "QtQuick")):
        return "pyside-setup/qtdeclarative-bindings"
    if stem.startswith("QtMultimedia"):
        return "pyside-setup/qtmultimedia-bindings"
    return None


def qt_license_status(filename: str) -> str:
    """Classify known GPL-only Qt module prefixes without legal conclusions."""

    stem = Path(filename).stem
    if any(stem.startswith(prefix) for prefix in GPL_ONLY_PREFIXES):
        return "GPL-ONLY-RISK"
    if stem.startswith(("Qt6", "Qt", "PySide", "Shiboken", "shiboken")):
        return "LGPL-OR-GPL-CANDIDATE"
    return "UNKNOWN"


def _runtime_scope(path: Path) -> str | None:
    lowered_parts = [part.lower() for part in path.parts]
    lowered_name = path.name.lower()
    if "pyside6" not in lowered_parts and "shiboken6" not in lowered_parts:
        return None
    if "plugins" in lowered_parts:
        return "plugin"
    if "qml" in lowered_parts:
        return "qml"
    if "translations" in lowered_parts:
        return "translation"
    if lowered_name.endswith((".dll", ".pyd", ".exe", ".json", ".zip")):
        return "runtime"
    return None


def _module_name(path: Path) -> str:
    stem = path.stem
    if stem.startswith("Qt6"):
        return re.sub(r"(?i)_debug$", "", stem)
    if stem.startswith("Qt") and path.suffix.lower() == ".pyd":
        return f"PySide6.{stem}"
    lowered = [part.lower() for part in path.parts]
    if "plugins" in lowered:
        index = lowered.index("plugins")
        return f"plugin:{path.parts[index + 1]}" if index + 1 < len(path.parts) else "plugin"
    if "qml" in lowered:
        index = lowered.index("qml")
        tail = path.parts[index + 1 : -1]
        return f"qml:{'.'.join(tail[:3])}" if tail else "qml"
    if "shiboken6" in lowered:
        return "shiboken6"
    return "PySide6"


def _necessity(path: Path, module: str, scope: str) -> tuple[str, str]:
    if any(module.startswith(required) for required in STATIC_USED_MODULES):
        return "LIKELY_REQUIRED", "Python/QML static import or transitive runtime map"
    lowered = [part.lower() for part in path.parts]
    if scope == "plugin" and "plugins" in lowered:
        plugin_dir = path.parts[lowered.index("plugins") + 1]
        if plugin_dir.lower() in LIKELY_REQUIRED_PLUGIN_DIRS:
            return "LIKELY_REQUIRED", "runtime plugin category used by current UI/media stack"
    if scope == "qml" and any(
        token in module
        for token in ("qml:QtQuick", "qml:QtQml", "qml:QtCore", "qml:QtMultimedia")
    ):
        return "LIKELY_REQUIRED", "matches current QML imports or direct transitive module"
    if scope == "translation":
        return "POSSIBLY_UNUSED", "no explicit translation loading found"
    return "POSSIBLY_UNUSED", "present in distribution without matching static import"


def _installed_roots() -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for package in ("PySide6", "shiboken6"):
        spec = importlib.util.find_spec(package)
        if spec and spec.origin:
            roots[package.lower()] = Path(spec.origin).resolve().parent
    return roots


def _origin_match(path: Path, installed_roots: dict[str, Path]) -> tuple[str, str | None]:
    lowered = [part.lower() for part in path.parts]
    for package in ("pyside6", "shiboken6"):
        if package not in lowered or package not in installed_roots:
            continue
        index = lowered.index(package)
        relative = Path(*path.parts[index + 1 :])
        installed = installed_roots[package] / relative
        if not installed.is_file():
            return "PySide6 wheel tree candidate", None
        digest = sha256_file(path)
        installed_digest = sha256_file(installed)
        if digest == installed_digest:
            return "PySide6 wheel tree SHA-256 match", installed_digest
        return "PySide6 wheel tree path match but SHA-256 differs", installed_digest
    return "UNKNOWN", None


def collect_qt_inventory(
    project_root: Path,
    dist_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Collect Qt runtime inventory and module/source analysis."""

    project_root = project_root.resolve()
    dist_path = dist_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    installed_roots = _installed_roots()
    records = []
    for path in sorted(dist_path.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file():
            continue
        scope = _runtime_scope(path)
        if scope is None:
            continue
        module = _module_name(path)
        necessity, evidence = _necessity(path, module, scope)
        origin, installed_digest = _origin_match(path, installed_roots)
        digest = sha256_file(path)
        records.append(
            {
                "path": display_path(path, project_root, dist_path),
                "size": path.stat().st_size,
                "sha256": digest,
                "scope": scope,
                "module": module,
                "necessity": necessity,
                "necessity_evidence": evidence,
                "origin": origin,
                "installed_wheel_file_sha256": installed_digest,
                "source_module": qt_source_module(path.name),
                "license_status": qt_license_status(path.name),
                "manual_confirmation_required": True,
            }
        )
    modules: dict[str, dict[str, Any]] = {}
    for record in records:
        module = record["module"]
        entry = modules.setdefault(
            module,
            {
                "files": 0,
                "bytes": 0,
                "necessity": record["necessity"],
                "license_status": record["license_status"],
                "source_modules": set(),
            },
        )
        entry["files"] += 1
        entry["bytes"] += record["size"]
        if record["source_module"]:
            entry["source_modules"].add(record["source_module"])
        if record["necessity"] == "LIKELY_REQUIRED":
            entry["necessity"] = "LIKELY_REQUIRED"
        if record["license_status"] == "GPL-ONLY-RISK":
            entry["license_status"] = "GPL-ONLY-RISK"
    normalized_modules = {
        name: {**value, "source_modules": sorted(value["source_modules"])}
        for name, value in sorted(modules.items())
    }
    try:
        pyside_version = importlib.metadata.version("PySide6")
        shiboken_version = importlib.metadata.version("shiboken6")
    except importlib.metadata.PackageNotFoundError:
        pyside_version = None
        shiboken_version = None
    payload = {
        "pyside6_version": pyside_version,
        "shiboken6_version": shiboken_version,
        "origin_summary": "Distribution files were compared with the installed PySide6 wheel tree by SHA-256.",
        "files": records,
        "modules": normalized_modules,
    }
    write_json(output_dir / "qt-runtime-inventory.json", payload)
    with (output_dir / "qt-runtime-hashes.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "path",
                "sha256",
                "size",
                "module",
                "scope",
                "necessity",
                "origin",
                "source_module",
                "license_status",
            ),
        )
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in writer.fieldnames})

    likely = [name for name, item in normalized_modules.items() if item["necessity"] == "LIKELY_REQUIRED"]
    unused = [name for name, item in normalized_modules.items() if item["necessity"] == "POSSIBLY_UNUSED"]
    gpl_risk = [name for name, item in normalized_modules.items() if item["license_status"] == "GPL-ONLY-RISK"]
    write_text(
        output_dir / "qt-module-analysis.md",
        "\n".join(
            [
                "# Qt Module Analysis",
                "",
                f"- 事实：PySide6 版本 `{pyside_version or 'UNKNOWN'}`；shiboken6 版本 `{shiboken_version or 'UNKNOWN'}`。",
                f"- 事实：发行目录内 Qt/PySide/shiboken 相关文件 `{len(records)}` 个。",
                f"- 推断：静态导入或直接传递依赖模块 `{len(likely)}` 组。",
                f"- 风险：`POSSIBLY_UNUSED` 模块 `{len(unused)}` 组；第一阶段不删除。",
                f"- 风险：发现 GPL-only 候选模块组 `{len(gpl_risk)}` 个；项目当前 GPL-3.0-or-later，但仍需补齐相应源码与声明。",
                "",
                "## Likely Required",
                *[f"- `{name}`" for name in likely],
                "",
                "## Possibly Unused",
                *[f"- `{name}`" for name in unused],
                "",
                "## GPL-only Risk Candidates",
                *[f"- `{name}`" for name in gpl_risk],
            ]
        )
        + "\n",
    )
    plugin_modules = {
        name: item
        for name, item in normalized_modules.items()
        if name.startswith("plugin:")
    }
    write_text(
        output_dir / "qt-plugin-analysis.md",
        "\n".join(
            [
                "# Qt Plugin Analysis",
                "",
                "- 事实：插件目录来自实际发行目录扫描。",
                "- 推断：platforms/imageformats/multimedia/styles/tls/networkinformation/platforminputcontexts 与当前桌面、多媒体和网络栈相关。",
                "- 风险：仅凭文件存在不能证明运行时实际加载；第一阶段不删除任何插件。",
                "",
                *[
                    f"- `{name}`: {item['files']} files, `{item['necessity']}`"
                    for name, item in plugin_modules.items()
                ],
            ]
        )
        + "\n",
    )
    source_modules = sorted(
        {
            source
            for record in records
            for source in ([record["source_module"]] if record["source_module"] else [])
            if not source.startswith("pyside-setup/")
        }
    )
    upstream_path = (
        project_root
        / "Tools"
        / "compliance"
        / "evidence"
        / f"qt-{pyside_version}-upstream.json"
    )
    upstream = load_json(upstream_path) if upstream_path.is_file() else {}
    if upstream:
        write_json(output_dir / "qt-upstream-evidence.json", upstream)
    wheel_verification_path = output_dir / "qt-wheel-verification.json"
    wheel_verification = (
        load_json(wheel_verification_path)
        if wheel_verification_path.is_file()
        else {}
    )
    pyside_source = upstream.get("pyside_source", {})
    pyside_source_archive = (
        project_root
        / "third_party"
        / "source-archives"
        / "qt"
        / str(pyside_source.get("filename", ""))
    )
    pyside_source_local_hash = (
        sha256_file(pyside_source_archive)
        if pyside_source.get("filename") and pyside_source_archive.is_file()
        else None
    )
    pyside_source_verified = bool(pyside_source_local_hash) and (
        pyside_source_local_hash
        == str(pyside_source.get("sha256", "")).upper()
    )
    exact_wheels = []
    for item in upstream.get("wheels", []):
        local_wheel = (
            project_root
            / "third_party"
            / "upstream-assets"
            / "qt"
            / str(item.get("filename", ""))
        )
        local_hash = (
            sha256_file(local_wheel)
            if item.get("filename") and local_wheel.is_file()
            else None
        )
        verified = bool(local_hash) and (
            local_hash == str(item.get("sha256", "")).upper()
        )
        exact_wheels.append(
            {
                **item,
                "local_archive": (
                    display_path(local_wheel, project_root)
                    if local_wheel.is_file()
                    else None
                ),
                "local_archive_sha256": local_hash,
                "local_archive_verified": verified,
            }
        )
    exact_wheel_archives_verified = (
        len(exact_wheels) == 4
        and all(item["local_archive_verified"] for item in exact_wheels)
    )
    upstream_source_modules = {
        item.get("module")
        for item in upstream.get("qt_source_modules", [])
    }
    source_module_coverage = set(source_modules).issubset(upstream_source_modules)
    qt_source_archives = []
    for item in upstream.get("qt_source_modules", []):
        local_archive = (
            project_root
            / "third_party"
            / "source-archives"
            / "qt"
            / str(item.get("filename", ""))
        )
        local_hash = (
            sha256_file(local_archive)
            if item.get("filename") and local_archive.is_file()
            else None
        )
        verified = bool(local_hash) and (
            local_hash == str(item.get("sha256", "")).upper()
        )
        qt_source_archives.append(
            {
                **item,
                "local_archive": (
                    display_path(local_archive, project_root)
                    if local_archive.is_file()
                    else None
                ),
                "local_archive_sha256": local_hash,
                "local_archive_verified": verified,
            }
        )
    qt_source_archives_verified = (
        len(qt_source_archives) == len(upstream.get("qt_source_modules", []))
        and bool(qt_source_archives)
        and all(item["local_archive_verified"] for item in qt_source_archives)
    )
    internal_third_party_sources = []
    for item in upstream.get("qt_internal_third_party_sources", []):
        local_archive = (
            project_root
            / "third_party"
            / "source-archives"
            / "qt"
            / str(item.get("filename", ""))
        )
        local_hash = (
            sha256_file(local_archive)
            if item.get("filename") and local_archive.is_file()
            else None
        )
        verified = bool(local_hash) and (
            local_hash == str(item.get("sha256", "")).upper()
        )
        internal_third_party_sources.append(
            {
                **item,
                "local_archive": (
                    display_path(local_archive, project_root)
                    if local_archive.is_file()
                    else None
                ),
                "local_archive_sha256": local_hash,
                "local_archive_verified": verified,
            }
        )
    internal_third_party_sources_verified = bool(
        internal_third_party_sources
    ) and all(
        item["local_archive_verified"]
        for item in internal_third_party_sources
    )
    materials_closed = all(
        (
            wheel_verification.get("byte_identical_to_exact_wheels") is True,
            exact_wheel_archives_verified,
            upstream.get("source_archives_identified") is True,
            upstream.get("license_document_snapshots_complete") is True,
            pyside_source_verified,
            source_module_coverage,
            qt_source_archives_verified,
            internal_third_party_sources_verified,
        )
    )
    source_requirements = {
        "qt_version": pyside_version,
        "exact_wheels": exact_wheels,
        "wheel_verification_status": wheel_verification.get(
            "status", "NOT_PERFORMED"
        ),
        "pyside_source": {
            **pyside_source,
            "local_archive": (
                display_path(pyside_source_archive, project_root)
                if pyside_source_archive.is_file()
                else None
            ),
            "local_archive_sha256": pyside_source_local_hash,
            "local_archive_verified": pyside_source_verified,
        },
        "qt_source_modules": qt_source_archives,
        "qt_internal_third_party_sources": internal_third_party_sources,
        "license_documents": upstream.get("license_documents", []),
        "source_module_coverage": source_module_coverage,
        "materials_closed": materials_closed,
        "unresolved": [
            "用运行时插件日志验证静态必要性推断",
            "Qt 模块最小化按所有者决定留待独立阶段，不在本轮删除",
        ],
    }
    write_json(output_dir / "qt-source-requirements.json", source_requirements)
    payload["upstream_evidence"] = {
        "exact_wheels_verified": wheel_verification.get(
            "byte_identical_to_exact_wheels"
        ),
        "exact_wheel_archives_verified": exact_wheel_archives_verified,
        "source_archives_identified": upstream.get(
            "source_archives_identified"
        ),
        "license_document_snapshots_complete": upstream.get(
            "license_document_snapshots_complete"
        ),
        "pyside_source_archive_verified": pyside_source_verified,
        "qt_source_archives_verified": qt_source_archives_verified,
        "qt_internal_third_party_sources_verified": (
            internal_third_party_sources_verified
        ),
        "source_module_coverage": source_module_coverage,
        "materials_closed": materials_closed,
    }
    write_json(output_dir / "qt-runtime-inventory.json", payload)
    write_text(
        output_dir / "qt-risk-analysis.md",
        "\n".join(
            [
                "# Qt / PySide6 Risk Analysis",
                "",
                "- 事实：当前运行库来自与本机 PySide6 wheel 树逐文件 SHA-256 对比的候选证据。",
                "- 事实：项目使用 PyInstaller onedir；Qt DLL 和插件以普通文件保留在 `_internal/PySide6`。",
                "- 推断：普通文件结构技术上支持替换，但尚未完成替换后启动/功能回归，不能宣称 LGPL 可替换义务已完全满足。",
                "- 风险：PyInstaller hook 收集了大量静态代码未导入的 QML/Qt 模块，包括 GPL-only 候选。",
                f"- 事实：发行 wheel 范围文件与 4 个精确 PyPI Windows wheel 逐字节一致 = `{wheel_verification.get('byte_identical_to_exact_wheels')}`。",
                f"- 事实：4 个精确 wheel 归档已保留并通过 PyPI SHA-256 = `{exact_wheel_archives_verified}`。",
                f"- 事实：22 个实际 Qt 源模块的官方源码归档已下载并通过官方 SHA-256 = `{qt_source_archives_verified}`。",
                f"- 事实：Qt Multimedia attribution 指向的 FFmpeg 7.1.3 精确源码已归档并验证 = `{internal_third_party_sources_verified}`。",
                f"- 事实：PySide/Shiboken 源码归档已下载并通过官方 SHA-256 = `{pyside_source_verified}`。",
                f"- 事实：Qt 官方许可、第三方代码、WebEngine 许可与 SBOM 文档快照已归档 = `{upstream.get('license_document_snapshots_complete')}`。",
                f"- 结论：本轮 Qt/PySide/Shiboken 许可证与源码材料闭合 = `{materials_closed}`。",
                "- 边界：按所有者决定，本轮不删除 POSSIBLY_UNUSED 或 GPL-only 候选模块；最小化留待独立阶段。",
            ]
        )
        + "\n",
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run Qt inventory collection."""

    args = build_parser().parse_args()
    collect_qt_inventory(args.project_root, args.dist_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

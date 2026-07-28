"""Generate the unified third-party manifest from collected local evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    display_path,
    load_json,
    parse_app_info,
    required_component_fields,
    sha256_file,
    source_contains,
    write_json,
)


def _empty_component(name: str, category: str) -> dict[str, Any]:
    component = {field: None for field in required_component_fields()}
    component.update(
        {
            "name": name,
            "category": category,
            "bundled_files": [],
            "binary_sha256": {},
            "evidence_files": [],
            "unresolved_questions": [],
        }
    )
    return component


def _bundled_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record
        for record in payload.get("files", [])
        if record.get("in_distribution")
    ]


def _runtime_identity(path: str) -> str:
    """Normalize report paths to the distribution-relative runtime suffix."""

    normalized = path.replace("\\", "/").lower()
    marker = "/_internal/"
    index = normalized.find(marker)
    return normalized[index:] if index >= 0 else normalized


def _repository_license(project_root: Path) -> str:
    readme = project_root / "README.md"
    text = readme.read_text(encoding="utf-8", errors="replace") if readme.is_file() else ""
    if "GPL-3.0-or-later" in text and (project_root / "LICENSE").is_file():
        return "GPL-3.0-or-later"
    return "UNDECIDED"


def _direct_python_components(
    python_payload: dict[str, Any],
    project_root: Path,
    dist_path: Path,
) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    skipped = {
        "pyside6",
        "pyside6-essentials",
        "pyside6-addons",
        "shiboken6",
    }
    for package in python_payload.get("requirements", []):
        normalized = package["name"].lower().replace("_", "-")
        if normalized in skipped:
            continue
        component = _empty_component(
            package["name"],
            "python-build-tool" if normalized == "pyinstaller" else "python-runtime",
        )
        version = package.get("installed_version")
        component.update(
            {
                "detected_version": version,
                "declared_license": package.get("license") or "UNKNOWN",
                "selected_license": None,
                "license_status": (
                    "DECLARED-PENDING-FILE-CHECK"
                    if package.get("license")
                    else "License status pending verification"
                ),
                "usage_mode": (
                    "build-time" if normalized == "pyinstaller" else "python-import"
                ),
                "dynamically_linked": None,
                "replaceable": normalized != "pyinstaller",
                "local_modifications": False,
                "evidence_files": [
                    "qt/python-packages.json",
                    *package.get("source_files", []),
                ],
                "unresolved_questions": [
                    "确认发行包内实际打包版本与本机构建环境版本一致",
                    "确认许可证全文和版权声明已纳入最终合规包",
                ],
            }
        )
        evidence_names = package.get("distribution_presence_evidence", [])
        component["bundled_files"] = [
            f"DIST/{name}" for name in evidence_names
        ]
        components.append(component)

    observed = [
        ("NumPy", "numpy", "BSD-3-Clause candidate"),
        ("Pillow", "PIL", "HPND candidate"),
        ("charset-normalizer", "charset_normalizer", "MIT candidate"),
    ]
    for display_name, marker, license_name in observed:
        paths = [
            path
            for path in dist_path.rglob("*")
            if marker.lower() in path.name.lower()
        ]
        if not paths:
            continue
        component = _empty_component(display_name, "python-runtime-transitive")
        try:
            import importlib.metadata

            version = importlib.metadata.version(display_name)
        except importlib.metadata.PackageNotFoundError:
            version = None
        component.update(
            {
                "detected_version": version,
                "declared_license": license_name,
                "license_status": "License status pending verification",
                "usage_mode": "python-import-or-transitive-bundle",
                "replaceable": True,
                "local_modifications": False,
                "bundled_files": [
                    display_path(path, project_root, dist_path)
                    for path in paths[:50]
                ],
                "evidence_files": ["qt/python-packages.json"],
                "unresolved_questions": [
                    "确认该组件是否为当前功能直接依赖或 PyInstaller 环境污染带入",
                    "确认完整许可证与第三方声明",
                ],
            }
        )
        components.append(component)
    return components


def generate_manifest(
    project_root: Path,
    dist_path: Path,
    report_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Generate and write the unified third-party manifest."""

    project_root = project_root.resolve()
    dist_path = dist_path.resolve()
    ffmpeg_files = load_json(report_root / "ffmpeg" / "ffmpeg-files.json")
    ffmpeg_prov = load_json(report_root / "ffmpeg" / "ffmpeg-provenance.json")
    ncmdump_files = load_json(report_root / "ncmdump" / "ncmdump-files.json")
    ncmdump_prov = load_json(report_root / "ncmdump" / "ncmdump-provenance.json")
    qt_payload = load_json(report_root / "qt" / "qt-runtime-inventory.json")
    qt_source_requirements = load_json(
        report_root / "qt" / "qt-source-requirements.json"
    )
    qt_wheel_verification = load_json(
        report_root / "qt" / "qt-wheel-verification.json"
    )
    python_payload = load_json(report_root / "qt" / "python-packages.json")
    release_inventory_path = report_root / "release-inventory.json"
    release_inventory = (
        load_json(release_inventory_path) if release_inventory_path.is_file() else {}
    )
    candidate_attempt_path = (
        report_root / "ffmpeg-self-build" / "candidate-build-attempt.json"
    )
    candidate_attempt = (
        load_json(candidate_attempt_path) if candidate_attempt_path.is_file() else {}
    )
    ffmpeg_b3_passed = candidate_attempt.get("result") == "PASS"

    all_ffmpeg_records = _bundled_records(ffmpeg_files)
    ffmpeg_records = [
        item
        for item in all_ffmpeg_records
        if item["path"].replace("\\", "/").lower().endswith(
            (
                "/tools/ffmpeg/bin/ffmpeg.exe",
                "/tools/ffmpeg/bin/ffprobe.exe",
                "/tools/ffmpeg/bin/ffplay.exe",
            )
        )
    ]
    qt_ffmpeg_records = [
        item for item in all_ffmpeg_records if item not in ffmpeg_records
    ]
    ffmpeg = _empty_component("FFmpeg", "external-binary")
    ffmpeg.update(
        {
            "bundled_files": [item["path"] for item in ffmpeg_records],
            "binary_sha256": {
                item["path"]: item["sha256"] for item in ffmpeg_records
            },
            "detected_version": ffmpeg_prov.get("detected_version"),
            "upstream_repository": ffmpeg_prov.get("upstream_repository"),
            "upstream_release": ffmpeg_prov.get("upstream_release"),
            "upstream_commit": ffmpeg_prov.get("upstream_commit"),
            "upstream_asset": ffmpeg_prov.get("upstream_asset"),
            "upstream_asset_sha256": ffmpeg_prov.get("upstream_asset_sha256"),
            "byte_identical_to_upstream": ffmpeg_prov.get(
                "byte_identical_to_upstream"
            ),
            "build_configuration": ffmpeg_files.get("configuration", {}).get("flags"),
            "build_provider": ffmpeg_prov.get("build_provider"),
            "source_package": ffmpeg_prov.get("source_package"),
            "source_sha256": ffmpeg_prov.get("source_sha256"),
            "declared_license": (
                "GPLv3 candidate"
                if ffmpeg_prov.get("classification") == "FFmpeg-GPL-CANDIDATE"
                else "UNKNOWN"
            ),
            "selected_license": "GPL-3.0-only",
            "license_status": "VERIFIED-GPL-3.0-BUILD",
            "copyright_notice": (
                "Copyright (c) 2000-2026 the FFmpeg developers; "
                "individual component notices remain in the corresponding source."
            ),
            "local_modifications": (
                False
                if ffmpeg_prov.get("byte_identical_to_upstream") is True
                else None
            ),
            "usage_mode": "subprocess",
            "dynamically_linked": False,
            "replaceable": True,
            "evidence_files": [
                "ffmpeg/ffmpeg-version.txt",
                "ffmpeg/ffmpeg-buildconf.txt",
                "ffmpeg/ffmpeg-package-README.txt",
                "ffmpeg/ffmpeg-files.json",
                "ffmpeg/ffmpeg-provenance.json",
                "ffmpeg/ffmpeg-asset-comparison.json",
                "ffmpeg/ffmpeg-dependency-inventory.json",
            ],
            "unresolved_questions": ffmpeg_prov.get("unresolved_questions", []),
        }
    )

    ncmdump_records = _bundled_records(ncmdump_files)
    ncmdump = _empty_component("ncmdump", "external-binary")
    ncmdump.update(
        {
            "bundled_files": [item["path"] for item in ncmdump_records],
            "binary_sha256": {
                item["path"]: item["sha256"] for item in ncmdump_records
            },
            "detected_version": ncmdump_prov.get("detected_version"),
            "upstream_repository": ncmdump_prov.get("upstream_repository"),
            "upstream_release": ncmdump_prov.get("upstream_release"),
            "upstream_commit": ncmdump_prov.get("upstream_commit"),
            "upstream_asset": ncmdump_prov.get("upstream_asset"),
            "upstream_asset_sha256": ncmdump_prov.get("upstream_asset_sha256"),
            "byte_identical_to_upstream": ncmdump_prov.get(
                "byte_identical_to_upstream"
            ),
            "build_configuration": ncmdump_prov.get("build_configuration"),
            "build_provider": "taurusxin/ncmdump GitHub Release",
            "source_package": ncmdump_prov.get("source_package"),
            "source_sha256": ncmdump_prov.get("source_sha256"),
            "declared_license": "MIT",
            "selected_license": "MIT",
            "license_status": (
                "VERIFIED-UPSTREAM-ASSET-SOURCE-AND-LICENSE"
                if ncmdump_prov.get("byte_identical_to_upstream") is True
                and ncmdump_prov.get("source_archive_verified") is True
                and ncmdump_prov.get("build_materials_closed") is True
                else "VERIFIED-LICENSE-FILE-INCLUDED"
            ),
            "copyright_notice": (
                "Upstream LICENSE.txt retains '[year] [fullname]' placeholders; "
                "Qonic Audio does not invent or replace the missing holder text."
            ),
            "local_modifications": (
                False
                if ncmdump_prov.get("byte_identical_to_upstream") is True
                else None
            ),
            "usage_mode": "subprocess",
            "dynamically_linked": (
                None
                if ncmdump_prov.get("taglib_linkage") == "UNKNOWN"
                else ncmdump_prov.get("taglib_linkage") == "DYNAMIC_LINK_CANDIDATE"
            ),
            "replaceable": True,
            "evidence_files": [
                "ncmdump/ncmdump-version.txt",
                "ncmdump/ncmdump-files.json",
                "ncmdump/ncmdump-provenance.json",
                "ncmdump/ncmdump-asset-comparison.md",
            ],
            "unresolved_questions": ncmdump_prov.get("unresolved_questions", []),
        }
    )
    ncmdump_dependency_metadata = {
        "TagLib": {
            "repository": "https://github.com/taglib/taglib",
            "declared_license": "LGPL-2.1-only OR MPL-1.1",
            "selected_license": "MPL-1.1",
        },
        "zlib": {
            "repository": "https://github.com/madler/zlib",
            "declared_license": "Zlib",
            "selected_license": "Zlib",
        },
        "utfcpp": {
            "repository": "https://github.com/nemtrif/utfcpp",
            "declared_license": "BSL-1.0",
            "selected_license": "BSL-1.0",
        },
    }
    ncmdump_dependencies = []
    for material in ncmdump_prov.get("build_materials", []):
        metadata = ncmdump_dependency_metadata.get(material.get("name"))
        if not metadata:
            continue
        component = _empty_component(
            material["name"], "ncmdump-statically-linked-dependency"
        )
        component.update(
            {
                "bundled_files": [item["path"] for item in ncmdump_records],
                "binary_sha256": {
                    item["path"]: item["sha256"] for item in ncmdump_records
                },
                "detected_version": material.get("version"),
                "upstream_repository": metadata["repository"],
                "upstream_release": material.get("version"),
                "upstream_commit": None,
                "upstream_asset": Path(
                    str(material.get("local_path", ""))
                ).name,
                "upstream_asset_sha256": material.get("sha256"),
                "byte_identical_to_upstream": None,
                "build_configuration": ncmdump_prov.get("build_configuration"),
                "build_provider": "vcpkg baseline "
                + str(ncmdump_prov.get("vcpkg_baseline")),
                "source_package": material.get("source_url"),
                "source_sha256": material.get("sha256"),
                "declared_license": metadata["declared_license"],
                "selected_license": metadata["selected_license"],
                "license_status": (
                    "VERIFIED-EXACT-SOURCE-ARCHIVE"
                    if material.get("verified")
                    else "SOURCE-ARCHIVE-VERIFICATION-PENDING"
                ),
                "copyright_notice": "见精确上游源码归档中的许可证与版权声明。",
                "local_modifications": False,
                "usage_mode": "statically linked into ncmdump.exe",
                "dynamically_linked": False,
                "replaceable": True,
                "evidence_files": [
                    "ncmdump/ncmdump-provenance.json",
                    "source-information/ncmdump-1.5.1-release.json",
                ],
                "unresolved_questions": [],
            }
        )
        ncmdump_dependencies.append(component)

    qt_files = qt_payload.get("files", [])
    microsoft_runtime_paths = {
        _runtime_identity(item["path"])
        for item in qt_wheel_verification.get("external_runtime_files", [])
    }
    qt_ffmpeg_paths = {
        _runtime_identity(item["path"]) for item in qt_ffmpeg_records
    }
    qt_component_files = [
        item
        for item in qt_files
        if _runtime_identity(item["path"]) not in microsoft_runtime_paths
        and _runtime_identity(item["path"]) not in qt_ffmpeg_paths
    ]
    qt = _empty_component("PySide6 / Qt 6 / shiboken6", "gui-runtime")
    qt.update(
        {
            "bundled_files": [item["path"] for item in qt_component_files],
            "binary_sha256": {
                item["path"]: item["sha256"]
                for item in qt_component_files
                if item["path"].lower().endswith((".dll", ".pyd", ".exe"))
            },
            "detected_version": qt_payload.get("pyside6_version"),
            "upstream_repository": "https://code.qt.io/cgit/pyside/pyside-setup.git/",
            "upstream_release": qt_payload.get("pyside6_version"),
            "upstream_commit": None,
            "upstream_asset": [
                item["filename"]
                for item in qt_source_requirements.get("exact_wheels", [])
            ],
            "upstream_asset_sha256": {
                item["filename"]: item["sha256"]
                for item in qt_source_requirements.get("exact_wheels", [])
            },
            "byte_identical_to_upstream": qt_wheel_verification.get(
                "byte_identical_to_exact_wheels"
            ),
            "build_configuration": None,
            "build_provider": "Exact official PyPI Windows wheels",
            "source_package": qt_source_requirements.get(
                "pyside_source", {}
            ).get("package_url"),
            "source_sha256": qt_source_requirements.get(
                "pyside_source", {}
            ).get("sha256"),
            "declared_license": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
            "selected_license": "GPL-3.0-only",
            "license_status": "VERIFIED-GPL-3.0-ROUTE",
            "copyright_notice": (
                "The Qt Company Ltd. and other Qt/PySide contributors; "
                "module-specific notices are preserved in the archived source and "
                "official third-party-code documents."
            ),
            "local_modifications": False,
            "usage_mode": "Python binding plus dynamically loaded Qt DLL/QML/plugins",
            "dynamically_linked": True,
            "replaceable": True,
            "evidence_files": [
                "qt/pyside6-version.txt",
                "qt/qt-runtime-inventory.json",
                "qt/qt-runtime-hashes.csv",
                "qt/qt-source-requirements.json",
                "qt/qt-upstream-evidence.json",
                "qt/qt-wheel-verification.json",
            ],
            "unresolved_questions": [
                "POSSIBLY_UNUSED 与 GPL-only 候选模块按所有者决定保留；最小化留待独立阶段",
            ],
            "qt_source_modules": qt_source_requirements.get(
                "qt_source_modules", []
            ),
            "license_documents": qt_source_requirements.get(
                "license_documents", []
            ),
            "qt_internal_third_party_sources": qt_source_requirements.get(
                "qt_internal_third_party_sources", []
            ),
        }
    )

    qt_internal_sources = qt_source_requirements.get(
        "qt_internal_third_party_sources", []
    )
    qt_ffmpeg_source = next(
        (
            item
            for item in qt_internal_sources
            if item.get("component") == "Qt Multimedia FFmpeg"
        ),
        {},
    )
    wheel_files_by_name = {
        Path(item["path"]).name.lower(): item
        for item in qt_wheel_verification.get("files", [])
        if item.get("wheel")
    }
    qt_ffmpeg_wheel_records = [
        wheel_files_by_name.get(Path(item["path"]).name.lower(), {})
        for item in qt_ffmpeg_records
    ]
    qt_ffmpeg_wheel_names = sorted(
        {
            item.get("wheel")
            for item in qt_ffmpeg_wheel_records
            if item.get("wheel")
        }
    )
    exact_wheels_by_name = {
        item["filename"]: item
        for item in qt_source_requirements.get("exact_wheels", [])
    }
    qt_ffmpeg = _empty_component(
        "Qt Multimedia FFmpeg",
        "gui-runtime-third-party",
    )
    qt_ffmpeg.update(
        {
            "bundled_files": [item["path"] for item in qt_ffmpeg_records],
            "binary_sha256": {
                item["path"]: item["sha256"] for item in qt_ffmpeg_records
            },
            "detected_version": qt_ffmpeg_source.get("version"),
            "upstream_repository": "https://github.com/FFmpeg/FFmpeg",
            "upstream_release": qt_ffmpeg_source.get("tag"),
            "upstream_commit": qt_ffmpeg_source.get("commit"),
            "upstream_asset": qt_ffmpeg_wheel_names,
            "upstream_asset_sha256": {
                name: exact_wheels_by_name.get(name, {}).get("sha256")
                for name in qt_ffmpeg_wheel_names
            },
            "byte_identical_to_upstream": bool(qt_ffmpeg_records)
            and len(qt_ffmpeg_wheel_records) == len(qt_ffmpeg_records)
            and all(item.get("byte_identical") for item in qt_ffmpeg_wheel_records),
            "build_configuration": None,
            "build_provider": "The Qt Company / official PySide6 wheel",
            "source_package": qt_ffmpeg_source.get("package_url"),
            "source_sha256": qt_ffmpeg_source.get("sha256"),
            "declared_license": qt_ffmpeg_source.get("license"),
            "selected_license": "LGPL-2.1-or-later",
            "license_status": "VERIFIED-QT-ATTRIBUTION-LGPL-ROUTE",
            "copyright_notice": qt_ffmpeg_source.get("copyright"),
            "local_modifications": False,
            "usage_mode": "Qt Multimedia FFmpeg backend dynamic libraries",
            "dynamically_linked": True,
            "replaceable": True,
            "evidence_files": [
                "qt/qt-wheel-verification.json",
                "qt/qt-source-requirements.json",
                (
                    "third_party/source-archives/qt/"
                    + str(qt_ffmpeg_source.get("filename", ""))
                ),
            ],
            "unresolved_questions": [
                "Qt attribution 指向的预构建 FFmpeg 构建脚本仓库尚未固定到独立 commit；本轮已闭合精确 wheel、attribution、许可证和 FFmpeg 7.1.3 源码。",
            ],
        }
    )

    msvc_evidence_path = (
        project_root
        / "Tools"
        / "compliance"
        / "evidence"
        / "microsoft-vc-runtime-14.44.35211.0.json"
    )
    msvc_evidence = (
        load_json(msvc_evidence_path) if msvc_evidence_path.is_file() else {}
    )
    qt_files_by_identity = {
        _runtime_identity(item["path"]): item for item in qt_files
    }
    msvc_records = [
        {
            **item,
            "path": qt_files_by_identity.get(
                _runtime_identity(item["path"]),
                item,
            )["path"],
        }
        for item in qt_wheel_verification.get("external_runtime_files", [])
    ]
    msvc = _empty_component(
        "Microsoft Visual C++ v14 Runtime",
        "system-runtime",
    )
    msvc.update(
        {
            "bundled_files": [item["path"] for item in msvc_records],
            "binary_sha256": {
                item["path"]: item["sha256"] for item in msvc_records
            },
            "detected_version": msvc_evidence.get("detected_version"),
            "upstream_repository": (
                "https://learn.microsoft.com/en-us/cpp/windows/"
                "latest-supported-vc-redist"
            ),
            "upstream_release": "v14 / 14.44.35211.0",
            "upstream_commit": None,
            "upstream_asset": None,
            "upstream_asset_sha256": None,
            "byte_identical_to_upstream": None,
            "build_configuration": None,
            "build_provider": "Microsoft Corporation",
            "source_package": None,
            "source_sha256": None,
            "declared_license": "Microsoft Software License Terms",
            "selected_license": "Microsoft Visual C++ v14 Redistributable terms",
            "copyright_notice": "Copyright Microsoft Corporation.",
            "license_status": msvc_evidence.get(
                "license_status",
                "PROPRIETARY-LICENSE-PENDING",
            ),
            "local_modifications": None,
            "usage_mode": "application-local dynamic runtime",
            "dynamically_linked": True,
            "replaceable": True,
            "evidence_files": [
                "qt/qt-wheel-verification.json",
                "licenses/microsoft/Microsoft-Visual-Cpp-V14-Redistributable-License-Terms.html",
                "licenses/microsoft/Microsoft-Visual-Cpp-Redistribution-Guidance.html",
            ],
            "unresolved_questions": [
                msvc_evidence.get("owner_confirmation_required")
            ],
        }
    )

    components = [
        ffmpeg,
        ncmdump,
        *ncmdump_dependencies,
        qt,
        qt_ffmpeg,
        msvc,
        *_direct_python_components(python_payload, project_root, dist_path),
    ]
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not ffmpeg_records:
        blockers.append(
            {
                "code": "FFMPEG_NOT_IN_AUDITED_DIST",
                "message": "审计发行目录未找到实际分发的 ffmpeg.exe。",
            }
        )
    if not ffmpeg_prov.get("exact_source_closed"):
        blockers.append(
            {
                "code": "FFMPEG_BUILD_CHAIN_INCOMPLETE",
                "message": (
                    "Qonic 自构建 B3 候选、精确源码、构建链、许可证与 Corresponding Source 已闭合；"
                    "B4 隔离 onedir/真实媒体回归和 B5 所有者替换审批尚未完成。"
                    if ffmpeg_b3_passed
                    else "FFmpeg 官方 Gyan 资产、核心源码、构建配置和包内 70 条依赖版本记录已闭合；"
                    "但提供者未公开 8.1.1 的精确脚本 revision、本地修改、补丁集及全部静态依赖对应源码。"
                ),
            }
        )
    if ffmpeg_prov.get("classification") == "FFmpeg-NONFREE-BLOCKER":
        blockers.append(
            {
                "code": "FFMPEG_NONFREE",
                "message": "FFmpeg 构建配置检测到 --enable-nonfree。",
            }
        )
    elif ffmpeg_prov.get("classification") == "FFmpeg-GPL-CANDIDATE":
        warnings.append(
            {
                "code": (
                    "FFMPEG_SELF_BUILD_B3_COMPLETED"
                    if ffmpeg_b3_passed
                    else "FFMPEG_GPL_ROUTE_SELECTED"
                ),
                "message": (
                    "正式发行仍保留逐字节验证通过的 Gyan GPLv3 full build；"
                    "Qonic 自构建 B3 候选已完成，B4/B5 前不得替换。"
                    if ffmpeg_b3_passed
                    else "项目所有者已选择保留逐字节验证通过的 Gyan GPLv3 full build。"
                ),
            }
        )
    if ncmdump_prov.get("byte_identical_to_upstream") is not True:
        asset_status = ncmdump_prov.get("asset_comparison_status")
        blockers.append(
            {
                "code": (
                    "NCMDUMP_WRONG_ASSET_TYPE"
                    if asset_status == "ASSET_TYPE_MISMATCH"
                    else "NCMDUMP_ASSET_NOT_VERIFIED"
                ),
                "message": (
                    "提供的官方 ZIP 仅含 libncmdump.dll，不含可与当前 ncmdump.exe 比对的 CLI EXE；未替换任何文件。"
                    if asset_status == "ASSET_TYPE_MISMATCH"
                    else "ncmdump 本地 EXE 尚未与官方 Windows CLI Release ZIP 解压文件逐字节比对。"
                ),
            }
        )
    if not ncmdump_prov.get("build_materials_closed"):
        warnings.append(
            {
                "code": "NCMDUMP_STATIC_DEPENDENCY_MATERIALS_INCOMPLETE",
                "message": "ncmdump 的 vcpkg baseline 或静态依赖源码材料尚未完整校验。",
            }
        )
    qt_gpl = sorted(
        {
            item["module"]
            for item in qt_files
            if item.get("license_status") == "GPL-ONLY-RISK"
        }
    )
    qt_unused = sorted(
        {
            item["module"]
            for item in qt_files
            if item.get("necessity") == "POSSIBLY_UNUSED"
        }
    )
    if not qt_source_requirements.get("materials_closed"):
        blockers.append(
            {
                "code": "QT_LICENSE_SOURCE_MATERIALS_INCOMPLETE",
                "message": "Qt/PySide6 完整许可、第三方声明、精确 wheel 与源码归档证据尚未闭合。",
            }
        )
    if qt_gpl:
        warnings.append(
            {
                "code": "QT_GPL_ONLY_MODULES_RETAINED",
                "message": f"发行包包含 {len(qt_gpl)} 组 GPL-only 模块；项目采用 GPL-3.0 路线，所有者决定本轮保留并推迟最小化。",
            }
        )
    if qt_unused:
        warnings.append(
            {
                "code": "QT_POSSIBLY_UNUSED_MODULES",
                "message": f"发行包包含 {len(qt_unused)} 组 POSSIBLY_UNUSED Qt/QML/插件模块。",
            }
        )
    if release_inventory.get("artifact_divergence"):
        blockers.append(
            {
                "code": "RELEASE_ARTIFACT_DIVERGENCE",
                "message": "同版本 Qonic 发行目录/归档存在不同哈希或外部工具清单差异。",
            }
        )
    if not release_inventory.get("authority_validation", {}).get("passed"):
        blockers.append(
            {
                "code": "RELEASE_AUTHORITY_VALIDATION_FAILED",
                "message": "审计输入未同时匹配所有者冻结的权威归档、哈希和展开目录。",
            }
        )
    if not any(
        item["path"].lower().endswith("tools/ffmpeg/bin/ffprobe.exe")
        for item in ffmpeg_records
    ):
        blockers.append(
            {
                "code": "FFPROBE_NOT_IN_AUDITED_DIST",
                "message": "审计发行目录缺少代码运行时会调用的 ffprobe.exe。",
            }
        )
    app_info = parse_app_info(project_root)
    repository_license = _repository_license(project_root)
    warnings.append(
        {
            "code": "MSVC_REDISTRIBUTION_LICENSE_CONFIRMATION",
            "message": "8 个 Microsoft VC Runtime DLL 已单列并归档许可条款；仍需所有者确认构建/分发受有效 Visual Studio 或 Build Tools 许可覆盖。",
        }
    )
    manual_decisions = [
        (
            "FFmpeg：完成 B4 隔离 onedir/真实媒体回归后生成 B5 替换提案，"
            "仅在项目所有者明确批准后替换正式二进制。"
            if ffmpeg_b3_passed
            else "FFmpeg：Gyan 未公开构建脚本、补丁集和静态依赖锁定材料；"
            "需向提供者索取或由所有者确认继续保持阻塞。"
        ),
        "Microsoft VC Runtime：确认当前构建与分发受有效 Visual Studio 或 Build Tools 许可覆盖。",
        "在所有 BLOCKER 关闭前不得发布最终合规声明或正式 Release。",
    ]
    manifest = {
        "schema_version": "1.0.0",
        "product": {
            "name": app_info.get("APP_DISPLAY_NAME", "Qonic Audio"),
            "description": app_info.get(
                "APP_DESCRIPTION", "Qonic Audio Converter & Editor"
            ),
            "version": app_info.get("APP_VERSION", "UNKNOWN"),
            "package_basename": app_info.get("APP_PACKAGE_BASENAME", "UNKNOWN"),
            "repository_license": repository_license,
        },
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "identity_algorithm": "SHA-256",
        "audited_distribution": release_inventory.get(
            "audited_distribution", "DIST"
        ),
        "release_authority": release_inventory.get("release_authority", {}),
        "components": components,
        "findings": blockers + warnings,
        "blockers": blockers,
        "warnings": warnings,
        "manual_decisions_required": manual_decisions,
    }
    write_json(output_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Generate the unified manifest."""

    args = build_parser().parse_args()
    generate_manifest(
        args.project_root,
        args.dist_path,
        args.report_root,
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Render the second-phase audit and owner-decision reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import load_json, write_text


def _codes(items: list[dict[str, Any]]) -> str:
    if not items:
        return "- 无。"
    return "\n".join(
        f"- `{item.get('code', 'UNKNOWN')}`：{item.get('message', '')}"
        for item in items
    )


def generate_audit_report(
    manifest: dict[str, Any],
    report_root: Path,
    output_path: Path,
) -> None:
    """Write the required 18-section second-phase audit report."""

    ffmpeg = load_json(report_root / "ffmpeg" / "ffmpeg-provenance.json")
    ncmdump = load_json(report_root / "ncmdump" / "ncmdump-provenance.json")
    qt = load_json(report_root / "qt" / "qt-runtime-inventory.json")
    qt_sources = load_json(report_root / "qt" / "qt-source-requirements.json")
    qt_wheels = load_json(report_root / "qt" / "qt-wheel-verification.json")
    release = load_json(report_root / "release-inventory.json")
    qt_modules = qt.get("modules", {})
    qt_unused = [
        name
        for name, item in qt_modules.items()
        if item.get("necessity") == "POSSIBLY_UNUSED"
    ]
    qt_gpl = [
        name
        for name, item in qt_modules.items()
        if item.get("license_status") == "GPL-ONLY-RISK"
    ]
    product = manifest["product"]
    authority = release.get("release_authority", {})
    authority_check = release.get("authority_validation", {})
    report = f"""# {product['name']} Third-Party Compliance Audit

> 第二阶段执行结果。本文是技术证据报告，不是法律意见；存在 BLOCKER 时不得表述为“完整合规”。

## 1. 执行摘要

- 项目正式名称为 `{product['name']}`，旧名称 `CherryQ Audio Converter` 只可出现在历史证据中。
- 唯一权威工件：`{release.get('audited_distribution', 'UNKNOWN')}`。
- 权威归档 SHA-256：`{(release.get('audited_archive') or {}).get('sha256', 'UNKNOWN')}`；所有者冻结值：`{authority.get('archive_sha256', 'UNKNOWN')}`。
- 权威工件校验：`{authority_check.get('passed')}`；同版本候选分叉：`{release.get('artifact_divergence')}`。
- 当前结论：`{len(manifest['blockers'])}` 个 BLOCKER、`{len(manifest['warnings'])}` 个 WARNING。

## 2. 当前发行结构

- 正式结构继续固定为 PyInstaller `onedir`，未引入 onefile。
- 权威归档及其对应展开目录是本报告唯一输入。
- 旧同名不同内容工件已移动到 `Release/Non_Authoritative/2026-07-24_pre_freeze/`，并以 `NOT_FOR_RELEASE.md` 标记；未删除。
- 构建中间目录不属于发布候选，不纳入权威身份判断。

## 3. 实际第三方二进制清单

- 权威展开目录含 FFmpeg、ffprobe、ncmdump、PySide6/Shiboken6、Qt DLL/QML/plugins 和 Microsoft VC Runtime。
- FFmpeg 运行路径为 `Tools/ffmpeg/bin/ffmpeg.exe`，Pitch 探测使用同目录 `ffprobe.exe`。
- ncmdump 运行路径为 `Tools/ncmdump/ncmdump.exe`，由子进程调用。
- Qt/PySide/Shiboken 已建立逐文件 SHA-256 清单；实际扫描 `{len(qt.get('files', []))}` 个文件。

## 4. FFmpeg 调查结果

- 当前版本：`{ffmpeg.get('detected_version') or 'UNKNOWN'}`；分类：`{ffmpeg.get('classification') or 'UNKNOWN'}`。
- 保留路线：Gyan GPLv3 full build；未替换 `ffmpeg.exe` 或 `ffprobe.exe`。
- 官方资产：`{ffmpeg.get('upstream_asset') or 'UNKNOWN'}`；SHA-256：`{ffmpeg.get('upstream_asset_sha256') or 'UNKNOWN'}`。
- 本地两个 EXE 与官方 Gyan 资产逐字节一致：`{ffmpeg.get('byte_identical_to_upstream')}`。
- FFmpeg 核心源码 commit：`{ffmpeg.get('upstream_commit') or 'UNKNOWN'}`；源码 SHA-256：`{ffmpeg.get('source_sha256') or 'UNKNOWN'}`。
- 提供者公开确认的环境：`{(ffmpeg.get('provider_build_environment') or {}).get('statement', 'UNKNOWN')}`。
- 官方包内 README SHA-256：`{ffmpeg.get('package_readme_sha256') or 'UNKNOWN'}`；已恢复 `{ffmpeg.get('package_dependency_version_count', 0)}` 条外部库版本记录。
- 阻断：Gyan 未公开 8.1.1 的精确脚本 revision、本地修改、补丁集和全部静态依赖对应源码；MABS 仅是提供者建议的复现候选，不能当作原构建证据。`exact_source_closed = {ffmpeg.get('exact_source_closed')}`。

## 5. ncmdump 调查结果

- 本地 EXE 自报版本：`{ncmdump.get('detected_version') or 'UNKNOWN'}`；SHA-256：`{ncmdump.get('local_binary_sha256') or 'UNKNOWN'}`。
- 正确 CLI 资产应为 `{ncmdump.get('upstream_asset') or 'UNKNOWN'}`，官方 SHA-256：`{ncmdump.get('upstream_asset_sha256') or 'UNKNOWN'}`。
- 用户提供资产：`{ncmdump.get('provided_asset') or 'UNKNOWN'}`；SHA-256：`{ncmdump.get('provided_asset_sha256') or 'UNKNOWN'}`。
- 比对状态：`{ncmdump.get('asset_comparison_status')}`；`byte_identical_to_upstream = {ncmdump.get('byte_identical_to_upstream')}`。
- 精确源码 commit：`{ncmdump.get('upstream_commit') or 'UNKNOWN'}`；源码 SHA-256：`{ncmdump.get('source_sha256') or 'UNKNOWN'}`；校验：`{ncmdump.get('source_archive_verified')}`。
- Windows 构建：`{ncmdump.get('build_configuration') or 'UNKNOWN'}`；vcpkg baseline：`{ncmdump.get('vcpkg_baseline') or 'UNKNOWN'}`。
- 结论：官方 CLI ZIP 内 EXE 与权威发行目录文件逐字节一致，保留当前 ncmdump.exe，未执行解压覆盖或替换。

## 6. PySide6 / Qt 调查结果

- PySide6 `{qt.get('pyside6_version') or 'UNKNOWN'}`，Shiboken6 `{qt.get('shiboken6_version') or 'UNKNOWN'}`。
- 四个精确 wheel 的官方文件名、URL、大小与 SHA-256 已固定；wheel 范围内 `{qt_wheels.get('matched_file_count', 0)}/{qt_wheels.get('wheel_scoped_file_count', 0)}` 个文件逐字节一致。
- `{len(qt_sources.get('qt_source_modules', []))}` 个实际 Qt 模块的官方源码归档及 SHA-256 已固定；PySide/Shiboken 对应源码归档已保存并验证。
- Qt Multimedia wheel 内 FFmpeg DLL 已单独归属为官方 attribution 指定的 FFmpeg 7.1.3；精确源码 commit/归档与 SHA-256 已保存，不再错误归入 Gyan 8.1.1 外部工具。
- Qt 官方许可、Qt 内部第三方代码、Qt WebEngine 第三方代码和 SBOM 文档已保存；`materials_closed = {qt_sources.get('materials_closed')}`。
- `{len(qt_gpl)}` 组 GPL-only 候选与 `{len(qt_unused)}` 组 `POSSIBLY_UNUSED` 按所有者决定保留；本轮未做模块最小化。

## 7. 当前许可证文件状态

- 项目自有代码采用 `{product['repository_license']}`。
- FFmpeg 按 GPL-3.0-only 路线记录；许可证、精确官方资产和核心源码已归档，提供者构建链仍阻断。
- ncmdump MIT 原文、官方 CLI 资产、精确 commit 源码和静态依赖材料已归档并校验。
- Qt/PySide/Shiboken 按 Community Edition GPL-3.0 路线记录，精确 wheels、源码和官方许可材料已闭合。
- 8 个 Microsoft VC Runtime DLL 已从 Qt wheel 比对范围中单列，许可条款已归档，仍需所有者确认分发许可覆盖。
- 补充扫描发现的 NumPy、Pillow 与 charset-normalizer 不属于本轮三组核心闭环；其许可证状态仍待独立验证，严格校验会保留 WARNING。

## 8. 已确认的事实

- 唯一发行工件、对应展开目录和 SHA-256 已冻结并通过检查。
- FFmpeg/ffprobe 与官方 Gyan 8.1.1 full build 逐字节一致。
- FFmpeg 核心源码 commit 和源码归档 SHA-256 已固定。
- 当前 ncmdump.exe 与官方 1.5.1 Windows amd64 CLI 资产逐字节一致。
- ncmdump 精确源码、Windows 构建工作流、vcpkg baseline、TagLib 2.0.2、zlib 1.3.1 与 utfcpp 4.0.6 已固定。
- Qt 精确 wheels、实际模块源码和官方许可材料已建立可复核清单。
- Qt Multimedia FFmpeg 7.1.3 attribution、版权、许可证与精确源码已建立可复核清单。

## 9. 尚未确认的事实

- Gyan 8.1.1 精确构建脚本 revision、本地修改、补丁集和全部静态依赖的对应源码。
- ncmdump 官方 GitHub Actions 的具体 runner 镜像版本与编译器补丁版本未在 Release 元数据中固定。
- Microsoft VC Runtime 的当前构建/分发是否由有效 Visual Studio 或 Build Tools 许可覆盖。
- NumPy、Pillow、charset-normalizer 的精确打包来源、必要性和最终许可证材料。
- Qt 模块真正最小集合；该事项已明确推迟到独立阶段。

## 10. 阻断问题

{_codes(manifest['blockers'])}

## 11. 普通警告

{_codes(manifest['warnings'])}

## 12. 本阶段已自动完成的整改

- 冻结并验证唯一权威归档与展开目录。
- 隔离同名不同内容旧工件并标记 `NOT_FOR_RELEASE`。
- 固定 FFmpeg 官方资产、核心源码、commit 和 SHA-256，完成两个 EXE 的流式逐字节比对。
- 完成 ncmdump 官方 CLI ZIP 逐字节比对，并固定精确源码、Windows 构建工作流及静态依赖源码。
- 固定 Qt/PySide/Shiboken 精确 wheels、源码与官方许可材料并完成 wheel 文件比对。
- 更新 Manifest、Notices、证据采集器、严格验证器输入和回归测试。

## 13. 必须由项目所有者继续处理的事项

{chr(10).join(f'- {item}' for item in manifest['manual_decisions_required'])}

## 14. 建议的后续顺序

1. 向 Gyan 索取 8.1.1 完整构建材料，或由所有者另行决定可复现自建路线。
2. 确认 Microsoft VC Runtime 分发许可覆盖。
3. 仅在 BLOCKER 清零后生成最终合规包和正式发布声明。

## 15. 当前最低风险依赖路线

- 继续使用已冻结的 onedir 权威工件。
- FFmpeg 保持当前逐字节验证通过的 Gyan GPL 构建，不擅自替换。
- ncmdump 保持当前逐字节验证通过的官方 1.5.1 CLI EXE，不做替换。
- Qt 保持现有模块全集与 GPL 路线；模块最小化独立提交、体积对比和完整回归。

## 16. 本阶段修改范围

- 合规工具与测试：`Tools/compliance/`。
- 审计输出：`compliance/`、`third_party/`、`LICENSES/`。
- 工件治理：`Release/External_Test/2026-07-24_b4edd4d/`、`Release/Non_Authoritative/`。
- 未修改应用运行逻辑、转换器、watcher、播放器核心、FFmpeg/ncmdump 二进制及 Qt 模块集合。

## 17. 明确未执行的操作

- 未替换 ffmpeg.exe、ffprobe.exe 或 ncmdump.exe。
- 未改为 PyInstaller onefile。
- 未删除 Qt DLL、QML 模块、插件或 GPL-only 候选模块。
- 未删除旧发行工件；仅移动并标记。
- 未发布 Release、tag、提交或推送远端。
- 未在存在 BLOCKER 时生成最终合规 ZIP。

## 18. 当前验收状态

- 权威工件：通过。
- FFmpeg 官方二进制对应：通过；提供者完整构建链：阻断。
- ncmdump：官方 CLI 资产、当前 EXE、精确源码与静态依赖材料验证通过。
- Qt/PySide/Shiboken 材料：通过；最小化：按决定推迟。
- 最终结论：第二阶段已完成可自动执行部分，但完整第三方依赖合规闭环尚未达成。
"""
    write_text(output_path, report)


def generate_owner_decisions(
    manifest: dict[str, Any],
    output_path: Path,
) -> None:
    """Record approved owner decisions and only the remaining gates."""

    product = manifest["product"]
    content = f"""# Owner Decisions

项目：`{product['name']}` / `{product['description']}`

状态：以下五项路线均已由项目所有者确认，不重新打开。

## 已批准决定

1. 唯一权威发行工件为 `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z` 及其对应展开目录；其他同版本差异工件仅隔离并标记 `NOT_FOR_RELEASE`。
2. 保留 FFmpeg 8.1.1 gyan.dev GPL 构建；未经再次批准不得替换 ffmpeg.exe 或 ffprobe.exe。
3. ncmdump 先逐字节比对；若不一致或资产类型错误立即停止，未经批准不得替换。
4. PyInstaller `onedir` 是唯一正式结构，本轮不维护 onefile。
5. 本轮保留 Qt `POSSIBLY_UNUSED` 与 GPL-only 候选模块；模块最小化作为后续独立阶段。

## 当前执行结果

- 权威工件验证通过，旧差异工件已隔离且未删除。
- FFmpeg/ffprobe 与官方 Gyan 8.1.1 full build 逐字节一致；核心 FFmpeg 源码已固定。
- ncmdump 官方 CLI ZIP 与权威发行目录 EXE 逐字节一致；保留当前 EXE，未解压覆盖或替换。
- ncmdump 精确 commit 源码、Windows 构建工作流、vcpkg baseline 与静态依赖源码已固定并校验。
- PySide6/Shiboken6 精确 wheels、实际 Qt 模块源码和官方许可材料已闭合。

## 仍需项目所有者或上游处理

{chr(10).join(f'- {item}' for item in manifest['manual_decisions_required'])}
"""
    write_text(output_path, content)

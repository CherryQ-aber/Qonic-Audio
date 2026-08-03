"""Generate THIRD_PARTY_NOTICES.md from the unified manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import load_json, write_text


def _format_value(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        if not value:
            return "未找到"
        preview = ", ".join(f"`{item}`" for item in value[:12])
        suffix = f"；另有 {len(value) - 12} 项见 Manifest" if len(value) > 12 else ""
        return preview + suffix
    if isinstance(value, dict):
        if not value:
            return "未找到"
        preview = ", ".join(
            f"`{key}`=`{item}`" for key, item in list(value.items())[:12]
        )
        suffix = f"；另有 {len(value) - 12} 项见 Manifest" if len(value) > 12 else ""
        return preview + suffix
    return str(value)


def generate_notices(manifest: dict[str, Any], output_path: Path) -> str:
    """Render factual notices without overstating unresolved license status."""

    product = manifest["product"]
    lines = [
        "# Third-Party Notices",
        "",
        f"Product: `{product['name']}`",
        f"Version: `{product['version']}`",
        "",
        "本文件由本地合规工具依据所有者冻结的唯一权威发行工件生成。",
        (
            "Manifest 中仍有 BLOCKER；本文件是当前证据清单，不构成“完整合规”声明。"
            if manifest.get("blockers")
            else "当前 Manifest 未报告 BLOCKER；仍应随每次发行重新执行校验。"
        ),
        "",
    ]
    for component in manifest["components"]:
        lines.extend(
            [
                f"## {component['name']}",
                "",
                f"- 组件类别：{_format_value(component['category'])}",
                f"- 实际版本：{_format_value(component['detected_version'])}",
                f"- 上游项目：{_format_value(component['upstream_repository'])}",
                f"- 上游发行/资产：{_format_value(component['upstream_release'])} / {_format_value(component['upstream_asset'])}",
                f"- 上游资产 SHA-256：{_format_value(component['upstream_asset_sha256'])}",
                f"- 实际分发文件：{_format_value(component['bundled_files'])}",
                f"- 上游声明许可证：{_format_value(component['declared_license'])}",
                f"- 本项目采用路线：{_format_value(component['selected_license'])}",
                f"- 版权所有者/声明：{_format_value(component.get('copyright_notice') or '见对应上游许可证与源码包')}",
                f"- 是否修改：{_format_value(component['local_modifications'])}",
                f"- 使用方式：{_format_value(component['usage_mode'])}",
                f"- 对应源码获取位置：{_format_value(component['source_package'])}",
                f"- 对应源码 SHA-256：{_format_value(component['source_sha256'])}",
                f"- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`",
                f"- 许可证状态：{_format_value(component['license_status'])}",
                "- 尚未解决的问题：",
                *[
                    f"  - {question}"
                    for question in component.get("unresolved_questions", [])
                ],
                "",
            ]
        )
    write_text(output_path, "\n".join(lines))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Generate notices from a manifest."""

    args = build_parser().parse_args()
    generate_notices(load_json(args.manifest), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

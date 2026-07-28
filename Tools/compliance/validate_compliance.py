"""Validate manifest structure and return 0/1/2/3 for pass/warning/blocker/error."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import required_component_fields


HASH_PATTERN = re.compile(r"^[0-9A-Fa-f]{64}$")
TOP_LEVEL_FIELDS = {
    "schema_version",
    "product",
    "generated_at",
    "identity_algorithm",
    "components",
    "findings",
    "blockers",
    "warnings",
    "manual_decisions_required",
}


def validate_manifest_data(
    manifest: dict[str, Any],
    *,
    strict: bool = False,
    max_age_hours: int = 168,
) -> tuple[list[str], list[str]]:
    """Return structural errors and ordinary warnings for a manifest."""

    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(TOP_LEVEL_FIELDS - set(manifest))
    if missing:
        errors.append(f"manifest 缺少顶层字段: {', '.join(missing)}")
    product = manifest.get("product")
    if not isinstance(product, dict):
        errors.append("product 必须是对象")
    else:
        for field in ("name", "version", "repository_license"):
            if not product.get(field):
                errors.append(f"product.{field} 缺失")
        if product.get("name") == "CherryQ Audio Converter":
            errors.append("manifest 仍使用旧项目名称 CherryQ Audio Converter")
    if manifest.get("identity_algorithm") != "SHA-256":
        errors.append("identity_algorithm 必须为 SHA-256")
    components = manifest.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components 必须是非空数组")
    else:
        required = set(required_component_fields())
        names: set[str] = set()
        for index, component in enumerate(components):
            if not isinstance(component, dict):
                errors.append(f"components[{index}] 必须是对象")
                continue
            component_missing = sorted(required - set(component))
            if component_missing:
                errors.append(
                    f"components[{index}] 缺少字段: {', '.join(component_missing)}"
                )
            name = component.get("name")
            if not name:
                errors.append(f"components[{index}].name 缺失")
            elif name in names:
                errors.append(f"组件名称重复: {name}")
            else:
                names.add(name)
            hashes = component.get("binary_sha256")
            if hashes is not None and not isinstance(hashes, dict):
                errors.append(f"{name or index}.binary_sha256 必须是对象或 null")
            elif isinstance(hashes, dict):
                for path, digest in hashes.items():
                    if not HASH_PATTERN.fullmatch(str(digest)):
                        errors.append(f"{name}: 非法 SHA-256: {path}")
            if component.get("byte_identical_to_upstream") is True:
                if not component.get("upstream_asset_sha256"):
                    errors.append(f"{name}: 声明逐字节一致但缺少上游资产 SHA-256")
                if not hashes:
                    errors.append(f"{name}: 声明逐字节一致但缺少本地二进制 SHA-256")
            if strict and component.get("license_status") in (
                None,
                "UNKNOWN",
                "License status pending verification",
            ):
                warnings.append(f"{name}: 许可证状态仍待验证")
    for field in ("findings", "blockers", "warnings", "manual_decisions_required"):
        if field in manifest and not isinstance(manifest[field], list):
            errors.append(f"{field} 必须是数组")
    generated = manifest.get("generated_at")
    if strict and generated:
        try:
            timestamp = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                warnings.append(
                    f"manifest 已超过 {max_age_hours} 小时未重新生成"
                )
        except ValueError:
            errors.append("generated_at 不是有效 ISO 8601 时间")
    return errors, warnings


def evaluate_exit_code(
    manifest: dict[str, Any],
    errors: list[str],
    validation_warnings: list[str],
) -> int:
    """Map validation state to the required process exit codes."""

    if errors or manifest.get("blockers"):
        return 2
    if validation_warnings or manifest.get("warnings"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-age-hours", type=int, default=168)
    return parser


def main() -> int:
    """Validate one manifest and print actionable diagnostics."""

    args = build_parser().parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: 无法读取 manifest: {exc}")
        return 3
    if not isinstance(manifest, dict):
        print("ERROR: manifest 根节点必须是对象")
        return 3
    errors, validation_warnings = validate_manifest_data(
        manifest,
        strict=args.strict,
        max_age_hours=args.max_age_hours,
    )
    for error in errors:
        print(f"BLOCKER: {error}")
    for blocker in manifest.get("blockers", []):
        print(f"BLOCKER: {blocker.get('code')}: {blocker.get('message')}")
    for warning in validation_warnings:
        print(f"WARNING: {warning}")
    for warning in manifest.get("warnings", []):
        print(f"WARNING: {warning.get('code')}: {warning.get('message')}")
    exit_code = evaluate_exit_code(manifest, errors, validation_warnings)
    print(
        f"SUMMARY: blockers={len(errors) + len(manifest.get('blockers', []))}, "
        f"warnings={len(validation_warnings) + len(manifest.get('warnings', []))}, "
        f"exit={exit_code}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

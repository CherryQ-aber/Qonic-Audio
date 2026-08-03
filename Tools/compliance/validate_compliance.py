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
FINAL_INVENTORY_FIELDS = {
    "schema_version",
    "generated_on",
    "identity_algorithm",
    "authoritative_release",
    "components",
    "native_file_ownership",
    "summary",
}
FINAL_COMPONENT_FIELDS = {
    "component",
    "component_type",
    "version",
    "source_package",
    "upstream_project",
    "package_provenance",
    "files",
    "hashes",
    "license",
    "license_files",
    "redistribution_requirement",
    "notice_requirement",
    "source_code_availability",
    "compliance_status",
}
FINAL_STATUSES = {
    "CLOSED",
    "WARNING",
    "BLOCKER",
    "OWNER_CONFIRMATION_REQUIRED",
    "NOT_APPLICABLE",
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


def validate_final_inventory_data(
    inventory: dict[str, Any],
    *,
    project_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Validate the release-scoped final inventory and its staged materials."""

    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(FINAL_INVENTORY_FIELDS - set(inventory))
    if missing:
        errors.append(f"final inventory 缺少顶层字段: {', '.join(missing)}")
        return errors, warnings
    if inventory.get("identity_algorithm") != "SHA-256":
        errors.append("final inventory identity_algorithm 必须为 SHA-256")
    components = inventory.get("components")
    if not isinstance(components, list) or not components:
        errors.append("final inventory components 必须是非空数组")
        return errors, warnings
    names: set[str] = set()
    referenced_licenses: set[str] = set()
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            errors.append(f"final inventory components[{index}] 必须是对象")
            continue
        component_missing = sorted(FINAL_COMPONENT_FIELDS - set(component))
        if component_missing:
            errors.append(
                f"final inventory components[{index}] 缺少字段: {', '.join(component_missing)}"
            )
            continue
        name = component["component"]
        if not name or name in names:
            errors.append(f"final inventory 组件名称为空或重复: {name!r}")
        names.add(name)
        status = component["compliance_status"]
        if status not in FINAL_STATUSES:
            errors.append(f"{name}: 非法合规状态 {status!r}")
        if status == "BLOCKER":
            errors.append(f"{name}: inventory 标记为 BLOCKER")
        if status in {"WARNING", "OWNER_CONFIRMATION_REQUIRED"}:
            warnings.append(f"{name}: {status}")
        hashes = component["hashes"]
        if not isinstance(hashes, dict) or not hashes:
            errors.append(f"{name}: 缺少分发文件 SHA-256")
        else:
            for path, digest in hashes.items():
                if not HASH_PATTERN.fullmatch(str(digest)):
                    errors.append(f"{name}: 非法 SHA-256: {path}")
        files = component["files"]
        if not isinstance(files, list) or not files:
            errors.append(f"{name}: 未列出实际发行文件")
        elif not set(files).issubset(set(hashes)):
            errors.append(f"{name}: files 未全部具有 SHA-256")
        license_files = component["license_files"]
        if not isinstance(license_files, list) or not license_files:
            errors.append(f"{name}: 缺少许可证 staging 材料")
        else:
            for item in license_files:
                referenced_licenses.add(str(item).replace("\\", "/"))
                if project_root and not (project_root / item).is_file():
                    errors.append(f"{name}: staging 许可证文件不存在: {item}")
        if status == "CLOSED":
            if not component["package_provenance"]:
                errors.append(f"{name}: CLOSED 组件缺少 package provenance")
            if not component["source_code_availability"]:
                errors.append(f"{name}: CLOSED 组件缺少 source availability")
    ownership = inventory["native_file_ownership"]
    if not isinstance(ownership, dict):
        errors.append("native_file_ownership 必须是对象")
    else:
        unassigned = ownership.get("unassigned_native_files")
        if not isinstance(unassigned, list):
            errors.append("native_file_ownership.unassigned_native_files 必须是数组")
        elif unassigned:
            errors.append(
                "UNKNOWN THIRD-PARTY COMPONENT: " + ", ".join(unassigned)
            )
    microsoft = next(
        (item for item in components if item.get("component") == "Microsoft VC Runtime"),
        None,
    )
    if not microsoft or microsoft.get("compliance_status") != "CLOSED":
        errors.append("Microsoft VC Runtime 必须保持 CLOSED")
    authority = inventory["authoritative_release"]
    if not isinstance(authority, dict) or not HASH_PATTERN.fullmatch(
        str(authority.get("archive_sha256", ""))
    ):
        errors.append("authoritative_release.archive_sha256 缺失或非法")
    if project_root:
        archive = project_root / str(authority.get("archive", ""))
        if not archive.is_file():
            errors.append("权威发行归档不存在")
        else:
            from finalize_third_party_compliance import sha256_file

            if sha256_file(archive) != authority["archive_sha256"]:
                errors.append("权威发行归档 SHA-256 已变化")
        stage_root = project_root / "docs" / "compliance" / "staging" / "licenses"
        if stage_root.is_dir():
            staged = {
                path.relative_to(project_root).as_posix()
                for path in stage_root.rglob("*")
                if path.is_file()
            }
            extra = sorted(staged - referenced_licenses)
            if extra:
                errors.append("licenses staging 引用了不存在的组件: " + ", ".join(extra))
        notices = project_root / "docs" / "compliance" / "THIRD_PARTY_NOTICES.md"
        if not notices.is_file():
            errors.append("THIRD_PARTY_NOTICES.md 不存在")
        else:
            text = notices.read_text(encoding="utf-8")
            missing_notices = [name for name in names if f"## {name}" not in text]
            if missing_notices:
                errors.append("THIRD_PARTY_NOTICES 缺少组件: " + ", ".join(missing_notices))
    return errors, warnings


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-age-hours", type=int, default=168)
    parser.add_argument("--final-inventory", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path("."))
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
    if args.final_inventory:
        try:
            final_inventory = json.loads(args.final_inventory.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: 无法读取 final inventory: {exc}")
            return 3
        if not isinstance(final_inventory, dict):
            print("ERROR: final inventory 根节点必须是对象")
            return 3
        final_errors, final_warnings = validate_final_inventory_data(
            final_inventory,
            project_root=args.project_root.resolve(),
        )
        errors.extend(final_errors)
        validation_warnings.extend(final_warnings)
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

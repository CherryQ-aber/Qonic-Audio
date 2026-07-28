"""Collect installed and declared Python package evidence without private paths."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import sys
from pathlib import Path
from typing import Any

from common import redact_text, run_command, write_json, write_text


REQUIREMENT_PATTERN = re.compile(
    r"^\s*([A-Za-z0-9_.-]+)\s*(?:==\s*([^;\s]+))?"
)


def read_requirements(path: Path, seen: set[Path] | None = None) -> list[dict[str, Any]]:
    """Read pinned or unpinned requirements recursively."""

    seen = seen or set()
    path = path.resolve()
    if path in seen or not path.is_file():
        return []
    seen.add(path)
    requirements: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            requirements.extend(read_requirements(path.parent / line[3:].strip(), seen))
            continue
        match = REQUIREMENT_PATTERN.match(line)
        if match:
            requirements.append(
                {
                    "name": match.group(1),
                    "declared_version": match.group(2),
                    "source_file": path.name,
                }
            )
    return requirements


def _metadata_value(metadata: importlib.metadata.PackageMetadata, key: str) -> Any:
    values = metadata.get_all(key) or []
    if key == "Project-URL":
        return values
    return values[0] if values else None


def collect_python_packages(
    project_root: Path,
    dist_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Collect declared/installed package versions and sanitized pip output."""

    project_root = project_root.resolve()
    dist_path = dist_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    declarations: list[dict[str, Any]] = []
    for name in ("requirements.txt", "requirements-dev.txt"):
        declarations.extend(read_requirements(project_root / name))
    merged: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        key = declaration["name"].lower().replace("_", "-")
        merged.setdefault(
            key,
            {
                "name": declaration["name"],
                "declared_versions": [],
                "source_files": [],
            },
        )
        if declaration["declared_version"]:
            merged[key]["declared_versions"].append(declaration["declared_version"])
        merged[key]["source_files"].append(declaration["source_file"])

    records = []
    for key, declaration in sorted(merged.items()):
        try:
            distribution = importlib.metadata.distribution(declaration["name"])
        except importlib.metadata.PackageNotFoundError:
            records.append(
                {
                    **declaration,
                    "installed_version": None,
                    "license": None,
                    "home_page": None,
                    "project_urls": [],
                    "installed": False,
                }
            )
            continue
        metadata = distribution.metadata
        records.append(
            {
                **declaration,
                "installed_version": distribution.version,
                "license": _metadata_value(metadata, "License")
                or _metadata_value(metadata, "License-Expression"),
                "license_files": metadata.get_all("License-File") or [],
                "home_page": _metadata_value(metadata, "Home-page"),
                "project_urls": _metadata_value(metadata, "Project-URL"),
                "installed": True,
            }
        )

    dist_names = {
        path.name.lower()
        for path in dist_path.rglob("*")
        if path.is_file() or path.is_dir()
    }
    for record in records:
        normalized = record["name"].lower().replace("-", "_")
        record["distribution_presence_evidence"] = sorted(
            name
            for name in dist_names
            if normalized in name.replace("-", "_")
        )[:50]
        record["possibly_bundled"] = bool(record["distribution_presence_evidence"])

    freeze = run_command(
        [sys.executable, "-m", "pip", "freeze"],
        cwd=project_root,
        project_root=project_root,
    )
    pyside_names = (
        "PySide6",
        "PySide6_Essentials",
        "PySide6_Addons",
        "shiboken6",
    )
    pyside_lines = []
    for name in pyside_names:
        try:
            dist = importlib.metadata.distribution(name)
            metadata = dist.metadata
            pyside_lines.extend(
                [
                    f"Name: {name}",
                    f"Version: {dist.version}",
                    f"License: {_metadata_value(metadata, 'License') or 'UNKNOWN'}",
                    "Location: <PYTHON_SITE_PACKAGES>",
                    "",
                ]
            )
        except importlib.metadata.PackageNotFoundError:
            pyside_lines.extend([f"Name: {name}", "Status: NOT INSTALLED", ""])
    payload = {
        "python_version": sys.version.split()[0],
        "requirements": records,
        "pip_freeze_returncode": freeze.returncode,
    }
    write_json(output_dir / "python-packages.json", payload)
    write_text(
        output_dir / "python-packages.txt",
        redact_text(freeze.combined_output, project_root),
    )
    write_text(output_dir / "pyside6-version.txt", "\n".join(pyside_lines))
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dist-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    """Run Python package evidence collection."""

    args = build_parser().parse_args()
    collect_python_packages(args.project_root, args.dist_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

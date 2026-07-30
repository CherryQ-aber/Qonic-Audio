"""Shared, standard-library-only helpers for the compliance toolchain."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


UTF8 = "utf-8"
TOOL_TIMEOUT_SECONDS = 30
SCAN_ROOT_NAMES = (
    "Tools",
    "tools",
    "Release",
    "release",
    "dist",
    "build",
    "bin",
    "resources",
    "Assets",
    "assets",
    "third_party",
    "vendor",
    "runtime",
)
IGNORED_SCAN_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "compliance",
    "Code_Review_Packages",
    "Codex_memory",
    # Self-build work and output trees are candidate/evidence material, not
    # part of the frozen formal distribution inventory.
    "output",
    "work",
}


class ComplianceError(RuntimeError):
    """Raised when evidence collection cannot complete safely."""


@dataclass(frozen=True)
class CommandResult:
    """A subprocess result with decoded, redacted output."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        """Return stdout and stderr without discarding either stream."""

        parts = [part.rstrip() for part in (self.stdout, self.stderr) if part.strip()]
        return "\n".join(parts) + ("\n" if parts else "")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the uppercase SHA-256 digest for one regular file."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"无法计算 SHA-256，文件不存在: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with stable LF newlines."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized, encoding=UTF8, newline="\n")


def write_json(path: Path, payload: Any) -> None:
    """Write deterministic, human-readable UTF-8 JSON."""

    write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def load_json(path: Path) -> Any:
    """Load one UTF-8 JSON document."""

    return json.loads(Path(path).read_text(encoding=UTF8))


def redact_text(text: str, project_root: Path | None = None) -> str:
    """Remove private Windows user and project absolute paths from captured output."""

    redacted = text
    replacements: list[tuple[str, str]] = []
    if project_root is not None:
        root = str(Path(project_root).resolve())
        replacements.extend(
            [
                (root, "<PROJECT_ROOT>"),
                (root.replace("\\", "/"), "<PROJECT_ROOT>"),
            ]
        )
    home = str(Path.home())
    replacements.extend(
        [
            (home, "<USER_HOME>"),
            (home.replace("\\", "/"), "<USER_HOME>"),
        ]
    )
    for source, replacement in sorted(replacements, key=lambda item: -len(item[0])):
        redacted = redacted.replace(source, replacement)
    redacted = re.sub(
        r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\r\n]+",
        r"<USER_HOME>",
        redacted,
    )
    return redacted


def run_command(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    timeout: int = TOOL_TIMEOUT_SECONDS,
    project_root: Path | None = None,
) -> CommandResult:
    """Run a command without a shell and retain both stdout and stderr."""

    command = [str(part) for part in args]
    environment = os.environ.copy()
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    environment.setdefault("PYTHONUTF8", "1")
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding=UTF8,
            errors="replace",
            timeout=timeout,
            shell=False,
            env=environment,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ComplianceError(f"命令超时（{timeout} 秒）: {command[0]}") from exc
    except OSError as exc:
        raise ComplianceError(f"命令无法启动: {command[0]}: {exc}") from exc
    return CommandResult(
        args=tuple(command),
        returncode=completed.returncode,
        stdout=redact_text(completed.stdout, project_root),
        stderr=redact_text(completed.stderr, project_root),
    )


def is_relative_to(path: Path, root: Path) -> bool:
    """Return whether path resolves inside root."""

    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


def display_path(path: Path, project_root: Path, dist_root: Path | None = None) -> str:
    """Return a stable relative path without exposing private absolute paths."""

    resolved = Path(path).resolve()
    project = Path(project_root).resolve()
    if is_relative_to(resolved, project):
        return resolved.relative_to(project).as_posix()
    if dist_root is not None and is_relative_to(resolved, dist_root):
        return f"DIST/{resolved.relative_to(Path(dist_root).resolve()).as_posix()}"
    return f"EXTERNAL/{resolved.name}"


def iter_scan_roots(project_root: Path, dist_root: Path | None = None) -> list[Path]:
    """Return existing project evidence roots plus an optional external dist root."""

    project_root = Path(project_root).resolve()
    roots: list[Path] = []
    seen: set[Path] = set()
    for name in SCAN_ROOT_NAMES:
        candidate = (project_root / name).resolve()
        if candidate.exists() and candidate not in seen:
            roots.append(candidate)
            seen.add(candidate)
    if dist_root is not None:
        candidate = Path(dist_root).resolve()
        if candidate.exists() and candidate not in seen:
            roots.append(candidate)
    return roots


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    """Yield regular files while skipping internal/report/cache directories."""

    for root in roots:
        try:
            is_file = root.is_file()
        except OSError:
            continue
        if is_file:
            yield root
            continue
        for current, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in IGNORED_SCAN_PARTS
            )
            current_path = Path(current)
            for filename in sorted(filenames):
                candidate = current_path / filename
                try:
                    is_file = candidate.is_file()
                except OSError:
                    # Docker/WSL work directories can contain inaccessible
                    # Windows reparse points. They are not local evidence files.
                    continue
                if is_file:
                    yield candidate


def find_named_files(
    project_root: Path,
    dist_root: Path | None,
    patterns: Sequence[str],
) -> list[Path]:
    """Find case-insensitive exact or wildcard file-name matches."""

    import fnmatch

    lowered_patterns = [pattern.lower() for pattern in patterns]
    matches: list[Path] = []
    seen: set[Path] = set()
    for path in iter_files(iter_scan_roots(project_root, dist_root)):
        lowered = path.name.lower()
        if any(fnmatch.fnmatch(lowered, pattern) for pattern in lowered_patterns):
            resolved = path.resolve()
            if resolved not in seen:
                matches.append(resolved)
                seen.add(resolved)
    return sorted(matches, key=lambda item: str(item).lower())


def duplicate_groups(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group file records that have the same SHA-256 digest."""

    grouped: dict[str, list[str]] = {}
    for record in records:
        digest = record.get("sha256")
        path = record.get("path")
        if digest and path:
            grouped.setdefault(str(digest), []).append(str(path))
    return [
        {"sha256": digest, "paths": sorted(paths)}
        for digest, paths in sorted(grouped.items())
        if len(paths) > 1
    ]


def read_pe_imports(path: Path) -> list[str]:
    """Read imported DLL names from a PE32/PE32+ binary using only stdlib."""

    data = Path(path).read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        return []
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        return []
    coff_offset = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff_offset + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    optional_offset = coff_offset + 20
    if optional_offset + optional_size > len(data):
        return []
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic == 0x10B:
        data_directory_offset = optional_offset + 96
    elif magic == 0x20B:
        data_directory_offset = optional_offset + 112
    else:
        return []
    import_directory_offset = data_directory_offset + 8
    if import_directory_offset + 8 > optional_offset + optional_size:
        return []
    import_rva, _ = struct.unpack_from("<II", data, import_directory_offset)
    section_offset = optional_offset + optional_size
    sections: list[tuple[int, int, int, int]] = []
    for index in range(section_count):
        offset = section_offset + index * 40
        if offset + 40 > len(data):
            break
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        sections.append((virtual_address, virtual_size, raw_pointer, raw_size))

    def rva_to_offset(rva: int) -> int | None:
        for virtual_address, virtual_size, raw_pointer, raw_size in sections:
            span = max(virtual_size, raw_size)
            if virtual_address <= rva < virtual_address + span:
                return raw_pointer + (rva - virtual_address)
        return None

    descriptor_offset = rva_to_offset(import_rva)
    if descriptor_offset is None:
        return []
    imports: list[str] = []
    for index in range(4096):
        offset = descriptor_offset + index * 20
        if offset + 20 > len(data):
            break
        descriptor = struct.unpack_from("<IIIII", data, offset)
        if descriptor == (0, 0, 0, 0, 0):
            break
        name_offset = rva_to_offset(descriptor[3])
        if name_offset is None or name_offset >= len(data):
            continue
        end = data.find(b"\0", name_offset, min(name_offset + 512, len(data)))
        if end < 0:
            continue
        imports.append(data[name_offset:end].decode("ascii", errors="replace"))
    return sorted(set(imports), key=str.lower)


def pe_metadata(path: Path) -> dict[str, Any]:
    """Return architecture and imported-DLL evidence for a PE file."""

    data = Path(path).read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        return {"is_pe": False, "machine": None, "imports": []}
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        return {"is_pe": False, "machine": None, "imports": []}
    machine_value = struct.unpack_from("<H", data, pe_offset + 4)[0]
    machine_names = {
        0x014C: "x86",
        0x8664: "x86_64",
        0xAA64: "arm64",
    }
    return {
        "is_pe": True,
        "machine": machine_names.get(machine_value, f"UNKNOWN_0x{machine_value:04X}"),
        "imports": read_pe_imports(path),
    }


def source_contains(project_root: Path, pattern: str) -> list[str]:
    """Find a literal string in first-party Python, QML, spec, and build files."""

    matches: list[str] = []
    suffixes = {".py", ".qml", ".spec", ".ps1", ".md", ".txt"}
    excluded = {
        ".git",
        "Release",
        "release",
        "build",
        "dist",
        "compliance",
        "third_party",
        "Code_Review_Packages",
        "Codex_memory",
    }
    for current, dirnames, filenames in os.walk(project_root):
        dirnames[:] = sorted(name for name in dirnames if name not in excluded)
        for filename in sorted(filenames):
            path = Path(current) / filename
            if path.suffix.lower() not in suffixes:
                continue
            try:
                text = path.read_text(encoding=UTF8, errors="replace")
            except OSError:
                continue
            if pattern.lower() in text.lower():
                matches.append(display_path(path, project_root))
    return sorted(set(matches))


def parse_app_info(project_root: Path) -> dict[str, str]:
    """Read literal application constants without importing project code."""

    import ast

    path = Path(project_root) / "app_info.py"
    if not path.is_file():
        return {}
    tree = ast.parse(path.read_text(encoding=UTF8), filename=str(path))
    values: dict[str, str] = {}

    def evaluate(node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for item in node.values:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    parts.append(item.value)
                elif isinstance(item, ast.FormattedValue):
                    parts.append(evaluate(item.value))
                else:
                    raise ValueError("unsupported f-string item")
            return "".join(parts)
        raise ValueError("unsupported application constant")

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = evaluate(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, str):
            values[target.id] = value
    return values


def required_component_fields() -> tuple[str, ...]:
    """Return the common component fields required by the manifest schema."""

    return (
        "name",
        "category",
        "bundled_files",
        "binary_sha256",
        "detected_version",
        "upstream_repository",
        "upstream_release",
        "upstream_commit",
        "upstream_asset",
        "upstream_asset_sha256",
        "byte_identical_to_upstream",
        "build_configuration",
        "build_provider",
        "source_package",
        "source_sha256",
        "declared_license",
        "selected_license",
        "license_status",
        "local_modifications",
        "usage_mode",
        "dynamically_linked",
        "replaceable",
        "evidence_files",
        "unresolved_questions",
    )


def fail(message: str, exit_code: int = 3) -> "NoReturn":
    """Print a clear failure and exit with the tool-failure code."""

    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)

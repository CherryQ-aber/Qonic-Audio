"""Fail when public Git inputs contain local-only or privacy-sensitive data."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SYNTHETIC_FIXTURE_PREFIX = "tests/fixtures/synthetic_privacy/"
SYNTHETIC_ALLOWED_LITERALS = (
    "C:\\Users\\Synthetic User",
    "AKIA" + "IOSFODNN7EXAMPLE",
    "ghp_" + "abcdefghijklmnopqrstuvwxyz1234567890",
    'password = "synthetic-test-only"',
)
ALLOWED_LOCAL_READMES = {
    "Test_Files/README.md",
    "Test_Files/converted/README.md",
}
ALLOWED_BINARY_EVIDENCE_PREFIXES = (
    "docs/compliance/staging/artifacts/",
    "third_party/source-information/",
)
FORBIDDEN_DIRECTORIES = {
    ".codex",
    ".mypy_cache",
    ".pytest_cache",
    ".reasonix",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "cache",
    "codex_memory",
    "codex执行记录",
    "code_review_packages",
    "dist",
    "htmlcov",
    "logs",
    "music_input",
    "music_output",
    "recordings",
    "release",
    "screenshots",
    "temp",
    "venv",
}
FORBIDDEN_FILENAMES = {
    ".coverage",
    "config.json",
    "config.json.bak",
    "v3大版本总结_v4启动引用.md",
}
FORBIDDEN_SUFFIXES = {
    ".7z",
    ".aac",
    ".aiff",
    ".ape",
    ".dll",
    ".exe",
    ".flac",
    ".log",
    ".m4a",
    ".mp3",
    ".msi",
    ".ogg",
    ".opus",
    ".pdb",
    ".pem",
    ".wav",
    ".whl",
    ".wma",
    ".zip",
}
PLACEHOLDER_WORDS = {
    "changeme",
    "dummy",
    "example",
    "fake",
    "placeholder",
    "redacted",
    "replace_me",
    "synthetic",
    "test-only",
    "your_",
}

# Keep real identifiers split so the guard does not flag its own rule source.
PRIVATE_EMAILS = {"316983335" + "@" + "qq.com"}
OWNER_PATHS = {
    "\\".join(("C:", "Users", "Cherry Q")),
    "/".join(("C:", "Users", "Cherry Q")),
}

SECRET_PATTERNS = (
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
)
ASSIGNED_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)"
    r"\b\s*[:=]\s*[\"']?([^\"'\s#;]{8,})[\"']?"
)
CREDENTIAL_URL = re.compile(r"(?i)https?://[^/\s:@]+:[^@\s/]+@")
WINDOWS_USER_PATH = re.compile(
    r"(?i)\b[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]([^\\/\r\n]+)"
)


@dataclass(frozen=True, order=True)
class Violation:
    category: str
    path: str
    detail: str


def normalize_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_allowed_binary_evidence(path: str) -> bool:
    return path.startswith(ALLOWED_BINARY_EVIDENCE_PREFIXES)


def scan_path(path: str | Path) -> list[Violation]:
    normalized = normalize_path(path)
    lower = normalized.lower()
    parts = lower.split("/")
    violations: list[Violation] = []

    if normalized in ALLOWED_LOCAL_READMES:
        return violations
    if lower.startswith(SYNTHETIC_FIXTURE_PREFIX.lower()):
        return violations
    if lower.startswith("test_files/"):
        return [Violation("local test artifact", normalized, "Test_Files is local-only")]
    if any(part in FORBIDDEN_DIRECTORIES for part in parts[:-1]):
        violations.append(
            Violation("local-only path", normalized, "forbidden local/build/runtime directory")
        )
    if parts[-1] in FORBIDDEN_FILENAMES or parts[-1].startswith(".env."):
        violations.append(
            Violation("local configuration", normalized, "forbidden local configuration file")
        )
    if parts[-1] == ".env":
        violations.append(Violation("credential file", normalized, "tracked .env file"))

    forbidden_suffix = next(
        (
            suffix
            for suffix in FORBIDDEN_SUFFIXES
            if lower.endswith(suffix)
        ),
        None,
    )
    if lower.endswith(".tar.gz"):
        forbidden_suffix = ".tar.gz"
    if forbidden_suffix and not _is_allowed_binary_evidence(normalized):
        violations.append(
            Violation(
                "binary or generated artifact",
                normalized,
                f"tracked {forbidden_suffix} file is not an approved compliance artifact",
            )
        )
    return violations


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def scan_text(path: str | Path, text: str) -> list[Violation]:
    normalized = normalize_path(path)
    synthetic_fixture = normalized.lower().startswith(
        SYNTHETIC_FIXTURE_PREFIX.lower()
    )
    violations: list[Violation] = []

    for private_email in PRIVATE_EMAILS:
        if private_email.lower() in text.lower():
            violations.append(
                Violation("private email", normalized, "known private Git email")
            )
    normalized_text = text.replace("/", "\\").lower()
    for owner_path in OWNER_PATHS:
        if owner_path.replace("/", "\\").lower() in normalized_text:
            violations.append(
                Violation("owner path", normalized, "Owner Windows user path")
            )

    content_to_scan = text
    if synthetic_fixture:
        for allowed_literal in SYNTHETIC_ALLOWED_LITERALS:
            content_to_scan = content_to_scan.replace(allowed_literal, "<synthetic>")

    for match in WINDOWS_USER_PATH.finditer(content_to_scan):
        username = match.group(1).strip().lower()
        if username not in {"qt", "runneradmin", "<username>", "%username%"}:
            violations.append(
                Violation(
                    "local machine path",
                    normalized,
                    f"Windows user directory for {match.group(1)!r}",
                )
            )
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(content_to_scan):
            violations.append(Violation("credential", normalized, label))
    for match in ASSIGNED_SECRET.finditer(content_to_scan):
        if not _is_placeholder(match.group(2)):
            violations.append(
                Violation(
                    "credential",
                    normalized,
                    f"non-placeholder {match.group(1)} assignment",
                )
            )
    if CREDENTIAL_URL.search(content_to_scan):
        violations.append(
            Violation("credential", normalized, "URL contains embedded credentials")
        )
    return violations


def git_candidate_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _read_text_if_applicable(path: Path) -> str | None:
    with path.open("rb") as stream:
        prefix = stream.read(8192)
        if b"\0" in prefix:
            return None
        remainder = stream.read()
    return (prefix + remainder).decode("utf-8", errors="replace")


def scan_repository(
    repo_root: Path,
    candidate_files: Iterable[str] | None = None,
) -> list[Violation]:
    root = repo_root.resolve()
    files = list(candidate_files) if candidate_files is not None else git_candidate_files(root)
    violations: set[Violation] = set()
    for relative in files:
        normalized = normalize_path(relative)
        violations.update(scan_path(normalized))
        absolute = root / Path(normalized)
        if not absolute.is_file():
            continue
        text = _read_text_if_applicable(absolute)
        if text is not None:
            violations.update(scan_text(normalized, text))
    return sorted(violations)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()

    violations = scan_repository(args.repo_root)
    if violations:
        print("Repository hygiene check FAILED:")
        for item in violations:
            print(f"- [{item.category}] {item.path}: {item.detail}")
        return 1
    print("Repository hygiene check PASS: no prohibited public-repository inputs found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
from pathlib import Path


SUPPORTED_AUDIO_EXTENSIONS = {
    ".ncm": "NCM",
    ".mp3": "MP3",
    ".flac": "FLAC",
    ".wav": "WAV",
    ".m4a": "M4A",
    ".aac": "AAC",
    ".ogg": "OGG",
    ".opus": "OPUS",
    ".ape": "APE",
    ".aiff": "AIFF",
    ".aif": "AIFF",
    ".wma": "WMA",
    ".alac": "ALAC",
}

LRC_EXTENSIONS = {".lrc"}
DEFAULT_MAX_FILES = 1000


def scan_directory_preview(
    folder_path: str,
    recursive: bool = False,
    max_files: int = DEFAULT_MAX_FILES,
    *,
    stop_event=None,
    progress_callback=None,
) -> dict:
    """Return a read-only directory preview without touching watcher state."""

    normalized_folder = os.path.abspath(os.path.normpath(os.fspath(folder_path or "")))
    result = {
        "ok": False,
        "error": "",
        "folder_path": normalized_folder if folder_path else "",
        "recursive": bool(recursive),
        "total_entries": 0,
        "scanned_files": 0,
        "supported_count": 0,
        "unsupported_count": 0,
        "lrc_count": 0,
        "too_many_files": False,
        "cancelled": False,
        "items": [],
    }

    if not folder_path:
        result["error"] = "目录路径为空"
        return result

    folder = Path(normalized_folder)
    if not folder.exists():
        result["error"] = "目录不存在"
        return result
    if not folder.is_dir():
        result["error"] = "所选路径不是目录"
        return result

    max_items = _normalize_max_files(max_files)

    try:
        seen_paths: set[str] = set()
        for entry in _iter_entries(folder, bool(recursive)):
            if stop_event is not None and stop_event.is_set():
                result["cancelled"] = True
                result["error"] = "扫描已取消"
                return result

            result["total_entries"] += 1

            if len(result["items"]) >= max_items:
                result["too_many_files"] = True
                break

            item = _build_item(
                entry,
                root_folder=folder,
                recursive=bool(recursive),
            )
            if item is None:
                continue

            normalized_item_path = os.path.normcase(
                os.path.abspath(str(item.get("path") or ""))
            )
            if normalized_item_path and normalized_item_path in seen_paths:
                item["scan_status"] = "重复文件"
                item["skip_reason"] = "重复路径"
                item["can_add_to_queue"] = False
            elif normalized_item_path:
                seen_paths.add(normalized_item_path)

            result["items"].append(item)
            if item.get("is_directory"):
                continue

            result["scanned_files"] += 1
            if item["is_lrc"]:
                result["lrc_count"] += 1
            elif item["is_supported_audio"]:
                result["supported_count"] += 1
            else:
                result["unsupported_count"] += 1

            if progress_callback is not None and result["total_entries"] % 25 == 0:
                progress_callback(result.copy())
    except OSError as exc:
        result["error"] = f"扫描失败：{exc}"
        return result

    if result["too_many_files"]:
        result["error"] = f"扫描结果超过上限 {max_items}，已截断。"

    result["ok"] = True
    return result


def _iter_entries(folder: Path, recursive: bool):
    if not recursive:
        with os.scandir(folder) as iterator:
            entries = sorted(iterator, key=lambda item: item.name.lower())
            yield from entries
        return

    stack = [folder]
    while stack:
        current = stack.pop()
        with os.scandir(current) as iterator:
            entries = sorted(iterator, key=lambda item: item.name.lower())
        for entry in entries:
            yield entry
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
            except OSError:
                continue


def _build_item(entry, *, root_folder: Path, recursive: bool) -> dict | None:
    path = Path(entry.path)
    extension_with_dot = path.suffix.lower()
    extension = extension_with_dot.lstrip(".")
    is_directory = False
    is_file = False

    try:
        is_directory = entry.is_dir(follow_symlinks=False)
        is_file = entry.is_file(follow_symlinks=False)
    except OSError as exc:
        return _base_item(
            path,
            extension,
            skip_reason=f"无法访问：{exc}",
            is_directory=False,
            root_folder=root_folder,
        )

    if is_directory:
        return _base_item(
            path,
            extension,
            skip_reason="" if recursive else "目录项，当前未递归扫描",
            is_directory=True,
            root_folder=root_folder,
        )

    if not is_file:
        return _base_item(
            path,
            extension,
            skip_reason="非普通文件",
            is_directory=False,
            root_folder=root_folder,
        )

    size_bytes = _safe_size(path)
    is_lrc = extension_with_dot in LRC_EXTENSIONS
    is_supported_audio = extension_with_dot in SUPPORTED_AUDIO_EXTENSIONS
    is_ncm = extension_with_dot == ".ncm"
    skip_reason = ""
    if is_lrc:
        skip_reason = "歌词文件，仅作为匹配候选"
    elif not is_supported_audio:
        skip_reason = "不支持的扩展名"

    matching_lrc_path = _find_matching_lrc(path) if is_supported_audio else ""
    return {
        "path": str(path),
        "filename": path.name,
        "extension": extension,
        "format_label": SUPPORTED_AUDIO_EXTENSIONS.get(
            extension_with_dot,
            "LRC" if is_lrc else (extension.upper() if extension else "未知"),
        ),
        "size_text": format_file_size(size_bytes),
        "size_bytes": size_bytes,
        "is_supported_audio": is_supported_audio,
        "is_ncm": is_ncm,
        "is_lrc": is_lrc,
        "is_directory": False,
        "has_matching_lrc": bool(matching_lrc_path),
        "matching_lrc_path": matching_lrc_path,
        "skip_reason": skip_reason,
        "scan_status": "可加入队列" if is_supported_audio else "跳过",
        "queue_status": "未入队",
        "can_add_to_queue": bool(is_supported_audio),
        "relative_path": _relative_path(path, root_folder),
        "source": "scan_preview",
    }


def _base_item(
    path: Path,
    extension: str,
    *,
    skip_reason: str,
    is_directory: bool,
    root_folder: Path,
) -> dict:
    return {
        "path": str(path),
        "filename": path.name,
        "extension": extension,
        "format_label": "目录" if is_directory else (extension.upper() if extension else "未知"),
        "size_text": "-",
        "size_bytes": 0,
        "is_supported_audio": False,
        "is_ncm": False,
        "is_lrc": False,
        "is_directory": is_directory,
        "has_matching_lrc": False,
        "matching_lrc_path": "",
        "skip_reason": skip_reason,
        "scan_status": "跳过",
        "queue_status": "未入队",
        "can_add_to_queue": False,
        "relative_path": _relative_path(path, root_folder),
        "source": "scan_preview",
    }


def _relative_path(path: Path, root_folder: Path) -> str:
    try:
        return str(path.relative_to(root_folder))
    except ValueError:
        return path.name


def _find_matching_lrc(audio_path: Path) -> str:
    candidates = (
        audio_path.with_suffix(".lrc"),
        audio_path.with_suffix(".LRC"),
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return ""


def _safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _normalize_max_files(max_files: int) -> int:
    try:
        value = int(max_files)
    except (TypeError, ValueError):
        value = DEFAULT_MAX_FILES
    return max(1, min(value, 10000))


def format_file_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "-"

    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "-"

    units = ("B", "KB", "MB", "GB")
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.2f} {units[unit_index]}"

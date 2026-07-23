from __future__ import annotations

import logging
import os
from collections.abc import Iterable

from cache_manager import clear_cache, format_size, scan_cache
from logger import LOG_DIR, LOG_FILE, LOG_FORMAT


def _normalized(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(path))))


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([_normalized(path), _normalized(root)]) == _normalized(root)
    except (OSError, TypeError, ValueError):
        return False


def scan_log_storage(log_dir: str = LOG_DIR) -> dict:
    """Return regular log files without following links outside the log directory."""
    root = os.path.abspath(os.fspath(log_dir))
    os.makedirs(root, exist_ok=True)
    items: list[dict] = []

    for current_root, directories, filenames in os.walk(
        root, topdown=True, followlinks=False
    ):
        directories[:] = [
            name
            for name in directories
            if not os.path.islink(os.path.join(current_root, name))
        ]
        for filename in filenames:
            path = os.path.abspath(os.path.join(current_root, filename))
            if not _is_within(path, root) or os.path.islink(path):
                continue
            try:
                if not os.path.isfile(path):
                    continue
                size = os.path.getsize(path)
            except OSError:
                continue
            items.append(
                {
                    "id": os.path.relpath(path, root),
                    "label": os.path.relpath(path, root),
                    "path": path,
                    "size": size,
                    "size_text": format_size(size),
                }
            )

    items.sort(key=lambda item: item["label"].lower())
    total_size = sum(item["size"] for item in items)
    return {
        "total_size": total_size,
        "total_size_text": format_size(total_size),
        "total_files": len(items),
        "items": items,
    }


def scan_settings_storage() -> dict:
    return {
        "logs": scan_log_storage(),
        "cache": scan_cache(),
    }


def clear_selected_cache(category_ids: Iterable[str]) -> dict:
    return clear_cache(categories=list(category_ids))


def clear_log_storage(
    log_dir: str = LOG_DIR,
    active_log_file: str = LOG_FILE,
) -> dict:
    """Clear log files and restore the active root FileHandler afterwards."""
    root = os.path.abspath(os.fspath(log_dir))
    active_path = os.path.abspath(os.fspath(active_log_file))
    summary = scan_log_storage(root)
    targets = {item["path"] for item in summary["items"]}
    root_logger = logging.getLogger()
    detached_handlers: list[logging.FileHandler] = []

    for handler in tuple(root_logger.handlers):
        if not isinstance(handler, logging.FileHandler):
            continue
        base_filename = getattr(handler, "baseFilename", "")
        if base_filename and _is_within(base_filename, root):
            root_logger.removeHandler(handler)
            detached_handlers.append(handler)

    for handler in detached_handlers:
        try:
            handler.flush()
        finally:
            handler.close()

    deleted_files = 0
    freed_size = 0
    failures: list[dict[str, str]] = []
    try:
        for path in targets:
            if not _is_within(path, root) or os.path.islink(path):
                failures.append({"path": path, "error": "路径不在日志目录内"})
                continue
            try:
                size = os.path.getsize(path)
                os.remove(path)
                deleted_files += 1
                freed_size += size
            except FileNotFoundError:
                continue
            except OSError as exc:
                failures.append({"path": path, "error": str(exc)})
    finally:
        os.makedirs(root, exist_ok=True)
        if _is_within(active_path, root):
            file_handler = logging.FileHandler(active_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
            root_logger.addHandler(file_handler)

    return {
        "deleted_files": deleted_files,
        "freed_size": freed_size,
        "freed_size_text": format_size(freed_size),
        "failed_count": len(failures),
        "failures": failures,
    }

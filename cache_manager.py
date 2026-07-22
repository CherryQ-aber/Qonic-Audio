import os
import shutil
import stat

from config import (
    CACHE_DIR,
    CONFIG_FILE,
    NCM_TEMP_DIR,
    TEMP_DIR,
    get_cache_folder,
    get_cover_thumb_cache_folder,
    get_editor_output_folder,
    get_editor_temp_folder,
    get_metadata_cache_folder,
    get_ncm_temp_folder,
    get_output_folder,
    get_pitch_preview_folder,
    get_temp_folder,
    get_watch_folder,
    get_waveform_cache_folder,
)
from logger import logger


CACHE_CATEGORIES = {
    "ncm_temp": {
        "label": "NCM 临时解码缓存",
        "path": get_ncm_temp_folder(),
        "extra_paths": [NCM_TEMP_DIR],
    },
    "pitch_preview": {
        "label": "升降调试听缓存",
        "path": get_pitch_preview_folder(),
        "extra_paths": [],
    },
    "editor_temp": {
        "label": "音频编辑临时文件",
        "path": get_editor_temp_folder(),
        "extra_paths": [],
    },
    "general_temp": {
        "label": "通用临时缓存",
        "path": os.path.join(TEMP_DIR, "General"),
        "extra_paths": [],
    },
    "waveform": {
        "label": "波形缓存",
        "path": get_waveform_cache_folder(),
        "extra_paths": [],
    },
    "cover_thumbs": {
        "label": "封面缩略图缓存",
        "path": get_cover_thumb_cache_folder(),
        "extra_paths": [],
    },
    "metadata": {
        "label": "元数据缓存",
        "path": get_metadata_cache_folder(),
        "extra_paths": [],
    },
}


def _normalize_path(path):
    return os.path.normpath(os.path.abspath(os.fspath(path)))


def _normcase(path):
    return os.path.normcase(_normalize_path(path))


def _is_reparse_or_symlink(path):
    try:
        if os.path.islink(path):
            return True

        stat_result = os.lstat(path)
        attributes = getattr(stat_result, "st_file_attributes", 0)
        reparse_flag = getattr(os.stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0)

        if not reparse_flag:
            reparse_flag = 0x0400

        return bool(attributes & reparse_flag)
    except OSError:
        return False


def _is_within_directory(path, root):
    try:
        path_norm = _normcase(path)
        root_norm = _normcase(root)
        return os.path.commonpath([path_norm, root_norm]) == root_norm
    except (OSError, ValueError):
        return False


def _category_paths(category_data):
    paths = [category_data["path"]]
    paths.extend(category_data.get("extra_paths") or [])

    normalized_paths = []
    seen = set()

    for path in paths:
        normalized = _normalize_path(path)
        key = os.path.normcase(normalized)

        if key in seen:
            continue

        seen.add(key)
        normalized_paths.append(normalized)

    return normalized_paths


def get_cache_roots():
    return {
        "temp": _normalize_path(get_temp_folder()),
        "cache": _normalize_path(get_cache_folder()),
    }


def ensure_cache_dirs():
    for root in get_cache_roots().values():
        os.makedirs(root, exist_ok=True)

    for category_data in CACHE_CATEGORIES.values():
        for path in _category_paths(category_data):
            os.makedirs(path, exist_ok=True)


def is_safe_cache_path(path, protected_paths=None):
    if not path:
        return False

    try:
        normalized = _normalize_path(path)
    except (TypeError, ValueError, OSError):
        return False

    roots = get_cache_roots().values()

    if any(os.path.normcase(normalized) == os.path.normcase(_normalize_path(root)) for root in roots):
        return False

    if not any(_is_within_directory(normalized, root) for root in roots):
        return False

    if _is_protected_runtime_path(normalized, protected_paths):
        return False

    if _is_reparse_or_symlink(normalized):
        return False

    return True


def _empty_category_summary(category_id, category_data):
    return {
        "id": category_id,
        "label": category_data["label"],
        "path": _normalize_path(category_data["path"]),
        "size": 0,
        "files": 0,
        "directories": 0,
        "cleanable_size": 0,
        "cleanable_files": 0,
        "skipped_size": 0,
        "skipped_files": 0,
        "paths": _category_paths(category_data),
    }


def _scan_path(path, protected_paths=None):
    result = {
        "size": 0,
        "files": 0,
        "directories": 0,
        "cleanable_size": 0,
        "cleanable_files": 0,
        "skipped_size": 0,
        "skipped_files": 0,
        "skipped": 0,
    }

    if not os.path.exists(path):
        return result

    protected_paths = protected_paths or _normalized_protected_paths()

    if not is_safe_cache_path(path, protected_paths):
        logger.warning(f"缓存扫描跳过非安全路径: {path}")
        result["skipped"] += 1
        result["skipped_files"] += 1
        return result

    if os.path.isfile(path):
        try:
            size = os.path.getsize(path)
            result["size"] += size
            result["files"] += 1
            result["cleanable_size"] += size
            result["cleanable_files"] += 1
        except OSError:
            result["skipped"] += 1
            result["skipped_files"] += 1
        return result

    pending_directories = [path]
    while pending_directories:
        current_root = pending_directories.pop()
        try:
            entries = list(os.scandir(current_root))
        except OSError:
            result["skipped"] += 1
            result["skipped_files"] += 1
            continue

        for entry in entries:
            entry_path = entry.path
            try:
                stat_result = entry.stat(follow_symlinks=False)
            except OSError:
                result["skipped"] += 1
                result["skipped_files"] += 1
                continue

            attributes = getattr(stat_result, "st_file_attributes", 0)
            reparse_flag = getattr(os.stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
            is_link = stat.S_ISLNK(stat_result.st_mode) or bool(
                attributes & reparse_flag
            )
            if is_link or _is_protected_runtime_path(entry_path, protected_paths):
                logger.warning(f"缓存扫描跳过非安全路径: {entry_path}")
                result["skipped"] += 1
                result["skipped_files"] += 1
                continue

            if stat.S_ISDIR(stat_result.st_mode):
                result["directories"] += 1
                pending_directories.append(entry_path)
                continue
            if not stat.S_ISREG(stat_result.st_mode):
                result["skipped"] += 1
                result["skipped_files"] += 1
                continue

            size = stat_result.st_size
            result["size"] += size
            result["files"] += 1
            result["cleanable_size"] += size
            result["cleanable_files"] += 1

    return result


def scan_cache():
    logger.info("开始扫描缓存...")
    ensure_cache_dirs()

    categories = {}
    total_size = 0
    total_files = 0
    total_directories = 0
    cleanable_size = 0
    cleanable_files = 0
    skipped_size = 0
    skipped_files = 0
    skipped_count = 0

    for category_id, category_data in CACHE_CATEGORIES.items():
        category_summary = _empty_category_summary(category_id, category_data)

        for path in category_summary["paths"]:
            path_summary = _scan_path(path)
            category_summary["size"] += path_summary["size"]
            category_summary["files"] += path_summary["files"]
            category_summary["directories"] += path_summary["directories"]
            category_summary["cleanable_size"] += path_summary["cleanable_size"]
            category_summary["cleanable_files"] += path_summary["cleanable_files"]
            category_summary["skipped_size"] += path_summary["skipped_size"]
            category_summary["skipped_files"] += path_summary["skipped_files"]
            skipped_count += path_summary["skipped"]

        total_size += category_summary["size"]
        total_files += category_summary["files"]
        total_directories += category_summary["directories"]
        cleanable_size += category_summary["cleanable_size"]
        cleanable_files += category_summary["cleanable_files"]
        skipped_size += category_summary["skipped_size"]
        skipped_files += category_summary["skipped_files"]
        categories[category_id] = category_summary

    logger.info(
        "缓存扫描完成："
        f"共 {total_files} 个文件，{format_size(total_size)}；"
        f"可清理 {cleanable_files} 个文件，{format_size(cleanable_size)}"
    )

    return {
        "total_size": total_size,
        "total_files": total_files,
        "total_directories": total_directories,
        "cleanable_size": cleanable_size,
        "cleanable_files": cleanable_files,
        "skipped_size": skipped_size,
        "skipped_files": skipped_files,
        "skipped_count": skipped_count,
        "categories": categories,
    }


def get_cache_size():
    return scan_cache()["total_size"]


def format_size(size_bytes):
    size = float(max(0, int(size_bytes or 0)))

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"

            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} TB"


def _delete_path(path, protected_paths=None):
    if not os.path.exists(path):
        return {
            "deleted_files": 0,
            "deleted_dirs": 0,
            "freed_size": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "failures": [],
        }

    if not is_safe_cache_path(path, protected_paths):
        logger.warning(f"拒绝清理非安全缓存路径: {path}")
        return {
            "deleted_files": 0,
            "deleted_dirs": 0,
            "freed_size": 0,
            "skipped_count": 1,
            "failed_count": 0,
            "failures": [],
        }

    if os.path.isfile(path):
        try:
            size = os.path.getsize(path)
            os.remove(path)
            return {
                "deleted_files": 1,
                "deleted_dirs": 0,
                "freed_size": size,
                "skipped_count": 0,
                "failed_count": 0,
                "failures": [],
            }
        except OSError as e:
            logger.warning(f"缓存文件清理失败: {path} - {e}")
            return {
                "deleted_files": 0,
                "deleted_dirs": 0,
                "freed_size": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "failures": [f"{path}: {e}"],
            }

    scan_result = _scan_path(path, protected_paths)

    try:
        shutil.rmtree(path)
        return {
            "deleted_files": scan_result["files"],
            "deleted_dirs": scan_result["directories"] + 1,
            "freed_size": scan_result["size"],
            "skipped_count": scan_result["skipped"],
            "failed_count": 0,
            "failures": [],
        }
    except OSError as e:
        logger.warning(f"缓存目录清理失败: {path} - {e}")
        return {
            "deleted_files": 0,
            "deleted_dirs": 0,
            "freed_size": 0,
            "skipped_count": scan_result["skipped"],
            "failed_count": 1,
            "failures": [f"{path}: {e}"],
        }


def _merge_clear_result(target, source):
    for key in ("deleted_files", "deleted_dirs", "freed_size", "skipped_count", "failed_count"):
        target[key] += source.get(key, 0)

    target["failures"].extend(source.get("failures", []))


def _protected_paths():
    return [
        get_watch_folder(),
        get_output_folder(),
        get_editor_output_folder(),
        CONFIG_FILE,
        os.path.join(os.path.dirname(CONFIG_FILE), "Tools"),
        os.path.join(os.path.dirname(CONFIG_FILE), "Music_Output"),
    ]


def _normalized_protected_paths():
    config_path = _normcase(CONFIG_FILE)
    normalized_paths = []
    for protected_path in _protected_paths():
        if not protected_path:
            continue
        try:
            protected = _normalize_path(protected_path)
        except (TypeError, ValueError, OSError):
            continue
        normalized_paths.append(
            (protected, os.path.normcase(protected) != config_path)
        )
    return tuple(normalized_paths)


def _is_protected_runtime_path(path, protected_paths=None):
    try:
        normalized = _normalize_path(path)
    except (TypeError, ValueError, OSError):
        return True

    protected_paths = protected_paths or _normalized_protected_paths()
    for protected, protects_descendants in protected_paths:

        if os.path.normcase(normalized) == os.path.normcase(protected):
            return True

        if protects_descendants and _is_within_directory(normalized, protected):
            return True

    return False


def clear_cache(categories=None):
    logger.info("开始清理缓存...")
    ensure_cache_dirs()

    selected = list(categories or CACHE_CATEGORIES.keys())
    result = {
        "deleted_files": 0,
        "deleted_dirs": 0,
        "freed_size": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "failures": [],
        "categories": {},
        "protected_paths": [_normalize_path(path) for path in _protected_paths() if path],
    }

    protected_paths = _normalized_protected_paths()

    for category_id in selected:
        category_data = CACHE_CATEGORIES.get(category_id)

        if category_data is None:
            result["skipped_count"] += 1
            result["failures"].append(f"未知缓存类别: {category_id}")
            logger.warning(f"未知缓存类别，已跳过: {category_id}")
            continue

        category_result = {
            "label": category_data["label"],
            "path": _normalize_path(category_data["path"]),
            "deleted_files": 0,
            "deleted_dirs": 0,
            "freed_size": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "failures": [],
        }

        for category_path in _category_paths(category_data):
            if not os.path.isdir(category_path):
                os.makedirs(category_path, exist_ok=True)
                continue

            for entry_name in os.listdir(category_path):
                entry_path = os.path.join(category_path, entry_name)
                entry_result = _delete_path(entry_path, protected_paths)
                _merge_clear_result(category_result, entry_result)

        for path in _category_paths(category_data):
            os.makedirs(path, exist_ok=True)

        _merge_clear_result(result, category_result)
        result["categories"][category_id] = category_result
        logger.info(
            f"已清理{category_data['label']}："
            f"{format_size(category_result['freed_size'])}"
        )

    ensure_cache_dirs()
    logger.info(
        "缓存清理完成："
        f"释放 {format_size(result['freed_size'])}"
    )
    return result

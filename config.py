import json
import os
import shutil
import sys
import tempfile
import threading
import logging

from app_info import APP_DATA_DIR_NAME, APP_DISPLAY_NAME, APP_VERSION
from app_paths import APP_PATHS
from formats import DEFAULT_TARGET_FORMAT, normalize_target_format

APP_NAME = APP_DISPLAY_NAME
THEME_MODE_OPTIONS = (
    "light",
    "dark",
    "system",
    "black",
    "purple",
)

# =========================
# 程序与用户数据目录
# =========================
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = APP_PATHS.install_dir

# BASE_DIR is retained as the runtime-resource compatibility name used by
# existing modules. Mutable installed data is rooted separately below.
BASE_DIR = APP_DIR


USER_DATA_DIR = APP_PATHS.user_data_dir
CONFIG_DIR = APP_PATHS.user_config_dir
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CACHE_DIR = APP_PATHS.user_cache_dir
LOG_DIR = APP_PATHS.user_log_dir
TEMP_DIR = APP_PATHS.user_temp_dir

# Both locations have existed in test/portable/early-installer builds.  They
# remain read-only migration sources and are never deleted or modified.
LEGACY_CONFIG_FILES = tuple(
    dict.fromkeys(
        (
            os.path.join(USER_DATA_DIR, "config.json"),
            os.path.join(APP_DIR, "config.json"),
        )
    )
)
LEGACY_CONFIG_FILE = LEGACY_CONFIG_FILES[-1]

_CONFIG_LOCK = threading.RLock()
_config_logger = logging.getLogger("AudioConverter.Config")
_LAST_MIGRATION_EVENT = None



def resolve_app_path(*parts):
    direct_path = os.path.join(BASE_DIR, *parts)

    if os.path.exists(direct_path):
        return direct_path

    internal_path = os.path.join(BASE_DIR, "_internal", *parts)

    if os.path.exists(internal_path):
        return internal_path

    return direct_path


NCM_TEMP_DIR = os.path.join(TEMP_DIR, "NCM")
NCM_DECODE_TEMP_DIR = os.path.join(TEMP_DIR, "NCMDecode")
PITCH_PREVIEW_TEMP_DIR = os.path.join(TEMP_DIR, "PitchPreview")
EDITOR_TEMP_DIR = os.path.join(TEMP_DIR, "Editor")
GENERAL_TEMP_DIR = os.path.join(TEMP_DIR, "General")
WAVEFORM_CACHE_DIR = os.path.join(CACHE_DIR, "Waveform")
COVER_THUMB_CACHE_DIR = os.path.join(CACHE_DIR, "CoverThumbs")
METADATA_CACHE_DIR = os.path.join(CACHE_DIR, "Metadata")

if IS_FROZEN:
    DEFAULT_OUTPUT_ROOT = os.path.join(
        os.path.expanduser("~"),
        "Music",
        APP_DATA_DIR_NAME,
    )
else:
    DEFAULT_OUTPUT_ROOT = BASE_DIR

# =========================
# 默认配置
# =========================
DEFAULT_CONFIG = {
    "watch_folder": "C:/CloudMusic/VipSongsDownload",
    "output_folder": os.path.join(DEFAULT_OUTPUT_ROOT, "Music_Output"),
    "editor_output_folder": os.path.join(
        DEFAULT_OUTPUT_ROOT,
        "AudioEditor_Output",
    ),
    "editor_temp_folder": EDITOR_TEMP_DIR,
    "editor_browser_folder": "",
    "editor_project_folders": [],
    "editor_browser_collapsed": False,
    "editor_file_bar_mode": "fixed",
    "folder_browser_root": "",
    "folder_browser_favorites": [],
    "folder_browser_recent": [],
    "folder_browser_visible": True,
    "folder_browser_width": 260,
    "lyrics_timestamp_precision": "millisecond",
    "target_format": DEFAULT_TARGET_FORMAT,
    "create_format_subfolder": True,
    "preserve_relative_structure": False,
    "embed_lyrics_after_convert": True,
    "copy_lrc_to_output": False,
    "overwrite_existing_lyrics": False,
    "auto_start_monitor": True,
    "scan_existing_on_start": False,
    "theme_mode": "system",
    "first_launch_completed": False,
    "window_state": {
        "x": None,
        "y": None,
        "width": 1536,
        "height": 982,
        "maximized": False,
    },
    # UI 预留字段：当前 Audio Editor Beta 只做前端占位。
    # 现有 converter.py / watcher.py 后端不得读取这些字段。
    "pitch_shift_enabled": False,
    "pitch_shift_semitones": 0,
    "pitch_shift_preserve_tempo": True,
    "pitch_shift_engine": "ui_reserved",
    "audio_output_device_id": "",
    "audio_output_device_name": "",
}


def _merge_with_default(config_data):
    merged = DEFAULT_CONFIG.copy()

    if isinstance(config_data, dict):
        merged.update(config_data)

    if IS_FROZEN:
        # A portable build may leave absolute defaults beside the executable.
        # Preserve every user-selected path, but migrate those exact legacy
        # defaults so a Program Files installation remains writable.
        legacy_defaults = {
            "output_folder": os.path.join(APP_DIR, "Music_Output"),
            "editor_output_folder": os.path.join(APP_DIR, "AudioEditor_Output"),
            "editor_temp_folder": os.path.join(APP_DIR, "Temp", "Editor"),
        }
        installed_defaults = {
            "output_folder": DEFAULT_CONFIG["output_folder"],
            "editor_output_folder": DEFAULT_CONFIG["editor_output_folder"],
            "editor_temp_folder": DEFAULT_CONFIG["editor_temp_folder"],
        }
        for key, legacy_path in legacy_defaults.items():
            current_path = str(merged.get(key) or "")
            if os.path.normcase(os.path.abspath(current_path)) == os.path.normcase(
                os.path.abspath(legacy_path)
            ):
                merged[key] = installed_defaults[key]

    if merged.get("theme_mode") not in THEME_MODE_OPTIONS:
        merged["theme_mode"] = DEFAULT_CONFIG["theme_mode"]

    default_window_state = DEFAULT_CONFIG["window_state"]
    window_state = merged.get("window_state")
    if not isinstance(window_state, dict):
        window_state = {}
    normalized_window_state = dict(default_window_state)
    normalized_window_state.update(window_state)
    for key in ("x", "y"):
        try:
            value = normalized_window_state.get(key)
            normalized_window_state[key] = None if value is None else int(value)
        except (TypeError, ValueError):
            normalized_window_state[key] = None
    for key, fallback in (("width", 1536), ("height", 982)):
        try:
            normalized_window_state[key] = max(1, int(normalized_window_state.get(key)))
        except (TypeError, ValueError):
            normalized_window_state[key] = fallback
    normalized_window_state["maximized"] = _as_bool(
        normalized_window_state.get("maximized"), False
    )
    merged["window_state"] = normalized_window_state

    if merged.get("editor_file_bar_mode") not in {"fixed", "floating"}:
        merged["editor_file_bar_mode"] = DEFAULT_CONFIG["editor_file_bar_mode"]

    if merged.get("lyrics_timestamp_precision") not in {
        "centisecond",
        "millisecond",
    }:
        merged["lyrics_timestamp_precision"] = DEFAULT_CONFIG[
            "lyrics_timestamp_precision"
        ]

    merged["target_format"] = normalize_target_format(
        merged.get("target_format"),
        DEFAULT_TARGET_FORMAT,
    )

    project_folders = merged.get("editor_project_folders")

    if not isinstance(project_folders, list):
        project_folders = []

    project_folders = [
        str(folder)
        for folder in project_folders
        if isinstance(folder, str) and folder.strip()
    ]

    legacy_browser_folder = str(merged.get("editor_browser_folder") or "").strip()

    if legacy_browser_folder and legacy_browser_folder not in project_folders:
        project_folders.append(legacy_browser_folder)

    merged["editor_project_folders"] = project_folders

    for key, limit in (
        ("folder_browser_favorites", 32),
        ("folder_browser_recent", 12),
    ):
        raw_paths = merged.get(key)
        if not isinstance(raw_paths, list):
            raw_paths = []
        normalized_paths = []
        seen_paths = set()
        for raw_path in raw_paths:
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            normalized_path = os.path.abspath(os.path.normpath(raw_path))
            identity = os.path.normcase(normalized_path)
            if identity in seen_paths:
                continue
            seen_paths.add(identity)
            normalized_paths.append(normalized_path)
            if len(normalized_paths) >= limit:
                break
        merged[key] = normalized_paths

    root_path = str(merged.get("folder_browser_root") or "").strip()
    merged["folder_browser_root"] = (
        os.path.abspath(os.path.normpath(root_path))
        if root_path
        else ""
    )
    merged["folder_browser_visible"] = _as_bool(
        merged.get("folder_browser_visible"),
        True,
    )
    try:
        pane_width = int(merged.get("folder_browser_width", 260))
    except (TypeError, ValueError):
        pane_width = 260
    merged["folder_browser_width"] = max(220, min(360, pane_width))

    return merged


# =========================
# 读取配置
# =========================
def _looks_like_existing_user_config(data):
    if not isinstance(data, dict) or not data:
        return False
    durable_keys = {
        "watch_folder",
        "output_folder",
        "editor_output_folder",
        "target_format",
        "theme_mode",
        "audio_output_device_id",
        "editor_project_folders",
        "folder_browser_favorites",
        "first_launch_completed",
    }
    return any(key in data for key in durable_keys)


def _prepare_migrated_config(data):
    migrated = _merge_with_default(data)
    if _looks_like_existing_user_config(data):
        # A legacy config proves that this profile already used an older build.
        # Do not show the new-install prompt merely because the old schema did
        # not yet have a durable first-run field (or left its legacy default).
        migrated["first_launch_completed"] = True
    return migrated


def _write_config_atomic(config_data, destination=None):
    target = os.fspath(destination or CONFIG_FILE)
    config_dir = os.path.dirname(target) or "."
    os.makedirs(config_dir, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(
        prefix=".config.",
        suffix=".tmp",
        dir=config_dir,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            descriptor = None
            json.dump(config_data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        raise
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _migrate_legacy_config_if_needed():
    global _LAST_MIGRATION_EVENT
    if os.path.exists(CONFIG_FILE):
        return None

    for legacy_path in LEGACY_CONFIG_FILES:
        if os.path.normcase(os.path.abspath(legacy_path)) == os.path.normcase(
            os.path.abspath(CONFIG_FILE)
        ) or not os.path.isfile(legacy_path):
            continue
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            migrated = _prepare_migrated_config(legacy_data)
            _write_config_atomic(migrated)
            _config_logger.info(
                "Legacy config migration succeeded: %s -> %s",
                legacy_path,
                CONFIG_FILE,
            )
            _LAST_MIGRATION_EVENT = {
                "ok": True,
                "source": legacy_path,
                "destination": CONFIG_FILE,
                "error": "",
            }
            return migrated
        except Exception as exc:
            _config_logger.exception(
                "Legacy config migration failed: %s -> %s",
                legacy_path,
                CONFIG_FILE,
            )
            _LAST_MIGRATION_EVENT = {
                "ok": False,
                "source": legacy_path,
                "destination": CONFIG_FILE,
                "error": str(exc),
            }
            if "legacy_data" in locals():
                return _prepare_migrated_config(legacy_data)
    return None


def get_last_config_migration_event():
    return dict(_LAST_MIGRATION_EVENT) if _LAST_MIGRATION_EVENT else None


def load_config():
    with _CONFIG_LOCK:
        migrated = _migrate_legacy_config_if_needed()
        if migrated is not None:
            return _merge_with_default(migrated)
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _merge_with_default(data)
        except FileNotFoundError:
            return _merge_with_default({})
        except Exception:
            _config_logger.exception("User config load failed: %s", CONFIG_FILE)
            backup_path = CONFIG_FILE + ".bak"
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    return _merge_with_default(json.load(f))
            except Exception:
                return _merge_with_default({})


# =========================
# 保存配置
# =========================
def save_config(config_data):
    """Persist application settings with one recoverable backup.

    This is intentionally different from audio publishing: config.json is
    application state, so an atomic replace is appropriate once a complete
    temporary file and a single ``.bak`` copy have been written.  A failed
    write never truncates the previous configuration.
    """
    with _CONFIG_LOCK:
        merged = _merge_with_default(config_data)
        backup_path = CONFIG_FILE + ".bak"
        try:
            if os.path.isfile(CONFIG_FILE):
                shutil.copy2(CONFIG_FILE, backup_path)
            _write_config_atomic(merged)
            return merged
        except Exception:
            _config_logger.exception("User config save failed: %s", CONFIG_FILE)
            raise


def update_config(updates):
    """Merge a partial update onto the newest config under one process lock."""
    if not isinstance(updates, dict):
        raise TypeError("updates must be a dict")
    with _CONFIG_LOCK:
        latest = load_config()
        latest.update(updates)
        return save_config(latest)


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in ("true", "1", "yes", "y", "on"):
            return True

        if normalized in ("false", "0", "no", "n", "off", ""):
            return False

    return default


# =========================
# 动态配置读取接口
# =========================
def get_watch_folder():
    return load_config()["watch_folder"]


def get_output_folder():
    return load_config()["output_folder"]


def get_editor_output_folder():
    return load_config()["editor_output_folder"]


def get_temp_folder():
    return TEMP_DIR


def get_cache_folder():
    return CACHE_DIR


def get_ncm_temp_folder():
    return NCM_DECODE_TEMP_DIR


def get_pitch_preview_folder():
    return PITCH_PREVIEW_TEMP_DIR


def get_editor_temp_folder():
    return load_config()["editor_temp_folder"]


def get_editor_browser_folder():
    return str(load_config().get("editor_browser_folder") or "")


def get_editor_project_folders():
    folders = load_config().get("editor_project_folders") or []

    if not isinstance(folders, list):
        return []

    return [
        str(folder)
        for folder in folders
        if isinstance(folder, str) and folder.strip()
    ]


def get_waveform_cache_folder():
    return WAVEFORM_CACHE_DIR


def get_cover_thumb_cache_folder():
    return COVER_THUMB_CACHE_DIR


def get_metadata_cache_folder():
    return METADATA_CACHE_DIR


def get_target_format():
    return load_config()["target_format"]


def get_create_format_subfolder():
    return _as_bool(load_config().get("create_format_subfolder"), True)


def get_preserve_relative_structure():
    return _as_bool(load_config().get("preserve_relative_structure"), False)


def get_embed_lyrics_after_convert():
    return _as_bool(load_config().get("embed_lyrics_after_convert"), True)


def get_copy_lrc_to_output():
    return _as_bool(load_config().get("copy_lrc_to_output"), False)


def get_overwrite_existing_lyrics():
    return _as_bool(load_config().get("overwrite_existing_lyrics"), False)


def get_auto_start_monitor():
    return _as_bool(load_config().get("auto_start_monitor"), True)


def get_scan_existing_on_start():
    return _as_bool(load_config().get("scan_existing_on_start"), False)


def get_theme_mode():
    return load_config()["theme_mode"]


def get_audio_output_device_id():
    return str(load_config().get("audio_output_device_id") or "")


def get_audio_output_device_name():
    return str(load_config().get("audio_output_device_name") or "")


def is_first_launch_completed():
    return _as_bool(load_config().get("first_launch_completed"), False)


def is_valid_watch_folder(folder_path=None):
    target_folder = folder_path or get_watch_folder()
    return bool(target_folder) and os.path.isdir(target_folder)


def is_valid_output_folder(folder_path=None):
    target_folder = folder_path or get_output_folder()
    return bool(target_folder)


def find_watch_folder_candidates():
    home_dir = os.path.expanduser("~")
    candidates = [
        "C:/CloudMusic/VipSongsDownload",
        os.path.join(home_dir, "Music", "CloudMusic", "VipSongsDownload"),
        os.path.join(home_dir, "Music", "NetEase", "CloudMusic", "VipSongsDownload"),
        os.path.join(home_dir, "Documents", "CloudMusic", "VipSongsDownload"),
        os.path.join(home_dir, "Downloads", "CloudMusic", "VipSongsDownload"),
    ]

    for drive_letter in ("D", "E", "F"):
        candidates.append(f"{drive_letter}:/CloudMusic/VipSongsDownload")

    seen = set()
    existing_candidates = []

    for candidate in candidates:
        normalized = os.path.normpath(candidate)

        if normalized in seen:
            continue

        seen.add(normalized)

        if os.path.isdir(normalized):
            existing_candidates.append(normalized)

    return existing_candidates


# =========================
# 兼容旧代码的常量
# 说明：
# 这几个值只用于兼容当前尚未修改的模块。
# 后续 watcher.py / converter.py / gui.py
# 会逐步改为调用上面的动态 getter。
# =========================
WATCH_FOLDER = get_watch_folder()
OUTPUT_FOLDER = get_output_folder()
TARGET_FORMAT = get_target_format()

# =========================
# 外部工具路径
# =========================
NCMDUMP_PATH = resolve_app_path(
    "Tools",
    "ncmdump",
    "ncmdump.exe"
)

FFMPEG_PATH = resolve_app_path(
    "Tools",
    "ffmpeg",
    "bin",
    "ffmpeg.exe"
)

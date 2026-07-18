import json
import os
import shutil
import sys
import tempfile

from app_info import APP_DISPLAY_NAME, APP_VERSION
from formats import DEFAULT_TARGET_FORMAT, normalize_target_format

APP_NAME = APP_DISPLAY_NAME
THEME_MODE_OPTIONS = (
    "light",
    "dark",
    "system",
)

# =========================
# 程序基础目录
# =========================
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def resolve_app_path(*parts):
    direct_path = os.path.join(BASE_DIR, *parts)

    if os.path.exists(direct_path):
        return direct_path

    internal_path = os.path.join(BASE_DIR, "_internal", *parts)

    if os.path.exists(internal_path):
        return internal_path

    return direct_path


TEMP_DIR = resolve_app_path("Temp")
NCM_TEMP_DIR = os.path.join(TEMP_DIR, "NCM")
CACHE_DIR = resolve_app_path("Cache")
NCM_DECODE_TEMP_DIR = os.path.join(TEMP_DIR, "NCMDecode")
PITCH_PREVIEW_TEMP_DIR = os.path.join(TEMP_DIR, "PitchPreview")
EDITOR_TEMP_DIR = os.path.join(TEMP_DIR, "Editor")
GENERAL_TEMP_DIR = os.path.join(TEMP_DIR, "General")
WAVEFORM_CACHE_DIR = os.path.join(CACHE_DIR, "Waveform")
COVER_THUMB_CACHE_DIR = os.path.join(CACHE_DIR, "CoverThumbs")
METADATA_CACHE_DIR = os.path.join(CACHE_DIR, "Metadata")

# =========================
# 默认配置
# =========================
DEFAULT_CONFIG = {
    "watch_folder": "C:/CloudMusic/VipSongsDownload",
    "output_folder": os.path.join(BASE_DIR, "Music_Output"),
    "editor_output_folder": os.path.join(BASE_DIR, "AudioEditor_Output"),
    "editor_temp_folder": EDITOR_TEMP_DIR,
    "editor_browser_folder": "",
    "editor_project_folders": [],
    "editor_browser_collapsed": False,
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

    if merged.get("theme_mode") not in THEME_MODE_OPTIONS:
        merged["theme_mode"] = DEFAULT_CONFIG["theme_mode"]

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

    return merged


# =========================
# 读取配置
# =========================
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return _merge_with_default(data)

    except Exception:
        return DEFAULT_CONFIG.copy()


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
    merged = _merge_with_default(config_data)

    config_dir = os.path.dirname(CONFIG_FILE) or "."
    os.makedirs(config_dir, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(
        prefix=".config.",
        suffix=".tmp",
        dir=config_dir,
    )
    backup_path = CONFIG_FILE + ".bak"
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            descriptor = None
            json.dump(
                merged,
                f,
                indent=4,
                ensure_ascii=False,
            )
            f.flush()
            os.fsync(f.fileno())

        # Keep one bounded recovery point.  If this copy fails we leave the
        # live config untouched rather than replacing it without recovery.
        if os.path.isfile(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, backup_path)

        os.replace(temp_path, CONFIG_FILE)
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

    return merged


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

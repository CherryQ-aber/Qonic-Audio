import json
import os
import sys

APP_NAME = "CherryQ Audio Converter"
APP_VERSION = "3.5.1"

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

# =========================
# 默认配置
# =========================
DEFAULT_CONFIG = {
    "watch_folder": "C:/CloudMusic/VipSongsDownload",
    "output_folder": os.path.join(BASE_DIR, "Music_Output"),
    "target_format": "flac",
    "auto_start_monitor": True,
    "scan_existing_on_start": False,
}


def _merge_with_default(config_data):
    merged = DEFAULT_CONFIG.copy()

    if isinstance(config_data, dict):
        merged.update(config_data)

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
    merged = _merge_with_default(config_data)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            merged,
            f,
            indent=4,
            ensure_ascii=False
        )

    return merged


# =========================
# 动态配置读取接口
# =========================
def get_watch_folder():
    return load_config()["watch_folder"]


def get_output_folder():
    return load_config()["output_folder"]


def get_target_format():
    return load_config()["target_format"]


def get_auto_start_monitor():
    return bool(load_config()["auto_start_monitor"])


def get_scan_existing_on_start():
    return bool(load_config()["scan_existing_on_start"])


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

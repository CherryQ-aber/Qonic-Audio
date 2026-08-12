from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from PySide6.QtCore import QStandardPaths

from app_info import APP_DATA_DIR_NAME


USER_DATA_ROOT_ENV = "QONIC_USER_DATA_ROOT"


@dataclass(frozen=True)
class AppPaths:
    install_dir: str
    user_data_dir: str
    user_config_dir: str
    user_cache_dir: str
    user_log_dir: str
    user_temp_dir: str


def _absolute(path: str) -> str:
    return os.path.abspath(os.path.normpath(os.path.expanduser(path)))


def _install_dir() -> str:
    if bool(getattr(sys, "frozen", False)):
        return _absolute(os.path.dirname(sys.executable))
    return _absolute(os.path.dirname(__file__))


def _user_data_dir() -> str:
    override = str(os.environ.get(USER_DATA_ROOT_ENV) or "").strip()
    if override:
        return _absolute(override)

    standard_root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation
    )
    if not standard_root:
        standard_root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return _absolute(os.path.join(standard_root, APP_DATA_DIR_NAME))


def build_app_paths() -> AppPaths:
    user_data_dir = _user_data_dir()
    cache_dir = os.path.join(user_data_dir, "Cache")
    return AppPaths(
        install_dir=_install_dir(),
        user_data_dir=user_data_dir,
        user_config_dir=os.path.join(user_data_dir, "Config"),
        user_cache_dir=cache_dir,
        user_log_dir=os.path.join(user_data_dir, "Logs"),
        user_temp_dir=os.path.join(cache_dir, "Temp"),
    )


APP_PATHS = build_app_paths()


__all__ = ["APP_PATHS", "AppPaths", "USER_DATA_ROOT_ENV", "build_app_paths"]

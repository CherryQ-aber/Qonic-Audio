# 日志系统配置
import logging
import os

from config import BASE_DIR

LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "runtime.log")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

os.makedirs(LOG_DIR, exist_ok=True)


def _configure_root_logger():
    root_logger = logging.getLogger()

    if getattr(root_logger, "_audio_converter_configured", False):
        return root_logger

    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    root_logger._audio_converter_configured = True

    return root_logger


_configure_root_logger()

logger = logging.getLogger("AudioConverter")

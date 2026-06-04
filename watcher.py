# 监听文件夹，处理新文件
import os
import subprocess
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import NCMDUMP_PATH, get_watch_folder
from logger import logger

IGNORED_EXTENSIONS = (
    ".lrc",
    ".txt"
)

SUPPORTED_AUDIO_EXTENSIONS = (
    ".mp3",
    ".flac",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
)

SUPPORTED_TARGET_FORMATS = (
    "mp3",
    "flac",
    "wav",
    "aac",
    "ogg",
)

DECODED_EXTENSIONS = (
    ".mp3",
    ".flac",
    ".wav"
)

READING_STATUS = "读取中"
WAITING_STATUS = "等待处理"
PROCESSING_STATUS = "处理中"
COMPLETED_STATUS = "已完成"
FAILED_STATUS = "失败"
SKIPPED_STATUS = "已跳过"

TERMINAL_STATUSES = (
    COMPLETED_STATUS,
    FAILED_STATUS,
    SKIPPED_STATUS
)

CLEARABLE_TERMINAL_STATUSES = (
    COMPLETED_STATUS,
    FAILED_STATUS
)

STATUS_DISPLAY = {
    READING_STATUS: {
        "label": "读取中",
        "detail": "正在确认文件写入完成",
        "color": "#F2A900",
    },
    WAITING_STATUS: {
        "label": "等待处理",
        "detail": "已准备好转换",
        "color": "#2F80ED",
    },
    PROCESSING_STATUS: {
        "label": "处理中",
        "detail": "正在解码或转换",
        "color": "#9B51E0",
    },
    COMPLETED_STATUS: {
        "label": "已完成",
        "detail": "转换完成，可清除记录",
        "color": "#27AE60",
    },
    FAILED_STATUS: {
        "label": "失败",
        "detail": "可修复后重试",
        "color": "#EB5757",
    },
    SKIPPED_STATUS: {
        "label": "已跳过",
        "detail": "本次不处理",
        "color": "#828282",
    },
}

NON_PROTECTED_NCM_MARKERS = (
    "not netease protected file",
)

FILE_READY_MAX_CHECKS = 12
FILE_READY_INTERVAL = 1
FILE_READY_STABLE_HITS = 2

def _get_hidden_subprocess_kwargs():
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    return {
        "startupinfo": startupinfo,
        "creationflags": creationflags,
    }

processed_files = set()
pending_files = []
processed_files_lock = threading.Lock()
pending_files_lock = threading.Lock()
suppressed_generated_paths = set()
suppressed_generated_paths_lock = threading.Lock()


def get_status_display(status):
    fallback = {
        "label": status,
        "detail": "未知状态",
        "color": "#828282",
    }

    return STATUS_DISPLAY.get(status, fallback).copy()


def _build_pending_file(file_path, status):
    ext = os.path.splitext(file_path)[1]

    return {
        "path": file_path,
        "filename": os.path.basename(file_path),
        "format": ext.replace(".", "").upper(),
        "status": status,
        "target_format": None,
        "decoded_path": None,
        "generated_paths": []
    }


def _find_pending_file_unlocked(file_path):
    for file_info in pending_files:
        if file_info["path"] == file_path:
            return file_info

    return None


def _refresh_pending_file_unlocked(file_info, file_path, status):
    refreshed = _build_pending_file(file_path, status)
    file_info.clear()
    file_info.update(refreshed)


def _register_suppressed_generated_paths(paths):
    if not paths:
        return

    with suppressed_generated_paths_lock:
        suppressed_generated_paths.update(paths)


def _release_suppressed_generated_paths(paths):
    if not paths:
        return

    with suppressed_generated_paths_lock:
        for path in paths:
            suppressed_generated_paths.discard(path)


def _is_suppressed_generated_path(file_path):
    with suppressed_generated_paths_lock:
        return file_path in suppressed_generated_paths


def _is_processed_file_unlocked(file_path):
    return file_path in processed_files


def has_processed_file(file_path):
    with processed_files_lock:
        return _is_processed_file_unlocked(file_path)


def mark_processed_file(file_path):
    with processed_files_lock:
        if _is_processed_file_unlocked(file_path):
            return False

        processed_files.add(file_path)

    return True


def has_pending_file(file_path):
    with pending_files_lock:
        return _find_pending_file_unlocked(file_path) is not None


def get_pending_file_status(file_path):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            return None

        return file_info["status"]


def add_pending_file(file_path, status=WAITING_STATUS):
    new_file_info = _build_pending_file(file_path, status)

    with pending_files_lock:
        existing_file_info = _find_pending_file_unlocked(file_path)

        if existing_file_info is not None:
            if existing_file_info["status"] in TERMINAL_STATUSES:
                _release_suppressed_generated_paths(
                    existing_file_info.get("generated_paths", [])
                )
                _refresh_pending_file_unlocked(
                    existing_file_info,
                    file_path,
                    status
                )
                logger.info(f"文件重新加入待处理列表: {file_path}")
                return True

            logger.warning(f"文件已在待处理列表中，跳过重复加入: {file_path}")
            return False

        pending_files.append(new_file_info)

    logger.info(f"已加入待处理列表: {file_path} - 状态: {status}")
    return True


def set_pending_file_status(file_path, status):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法更新状态: {file_path}")
            return False

        file_info["status"] = status

    return True


def set_pending_file_runtime_data(file_path, decoded_path=None, generated_paths=None):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法更新运行时数据: {file_path}")
            return False

        file_info["decoded_path"] = decoded_path
        file_info["generated_paths"] = list(generated_paths or [])

    return True


def set_pending_file_target_format(file_path, target_format):
    normalized_format = None

    if target_format:
        normalized_format = target_format.lower()

        if normalized_format not in SUPPORTED_TARGET_FORMATS:
            logger.warning(f"不支持的目标格式，已忽略: {target_format}")
            return False

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法设置目标格式: {file_path}")
            return False

        if file_info["status"] in (PROCESSING_STATUS, COMPLETED_STATUS):
            logger.warning(f"当前状态不允许修改目标格式: {file_path}")
            return False

        file_info["target_format"] = normalized_format

    if normalized_format:
        logger.info(f"单文件目标格式已设置: {file_path} -> {normalized_format}")
    else:
        logger.info(f"单文件目标格式已恢复为跟随全局: {file_path}")

    return True


def remove_pending_file_by_path(file_path):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            return False

        generated_paths = list(file_info.get("generated_paths", []))
        pending_files.remove(file_info)

    _release_suppressed_generated_paths(generated_paths)
    clear_processed_file(file_path)
    return True


def remove_pending_file(file_info):
    file_path = file_info.get("path")

    if not file_path:
        return False

    return remove_pending_file_by_path(file_path)


def get_pending_files_snapshot():
    with pending_files_lock:
        return list(pending_files)


def _build_task_snapshot(file_info):
    task = dict(file_info)
    input_path = task.get("decoded_path") or task["path"]

    task["input_path"] = input_path
    task["is_ncm_task"] = bool(task.get("decoded_path"))
    task["target_format"] = task.get("target_format")
    task["can_convert"] = task["status"] == WAITING_STATUS
    task["can_retry"] = task["status"] == FAILED_STATUS
    task["can_change_target_format"] = task["status"] not in (
        PROCESSING_STATUS,
        COMPLETED_STATUS,
    )

    return task


def get_task_snapshots():
    with pending_files_lock:
        return [
            _build_task_snapshot(file_info)
            for file_info in pending_files
        ]


def get_convertible_tasks():
    return [
        task
        for task in get_task_snapshots()
        if task["can_convert"]
    ]


def get_retryable_tasks(file_paths=None):
    selected_paths = set(file_paths or [])

    return [
        task
        for task in get_task_snapshots()
        if task["can_retry"]
        and (not selected_paths or task["path"] in selected_paths)
    ]


def clear_processed_file(file_path):
    with processed_files_lock:
        if not _is_processed_file_unlocked(file_path):
            return False

        processed_files.remove(file_path)

    return True


def skip_pending_file(file_path):
    updated = set_pending_file_status(file_path, SKIPPED_STATUS)

    if updated:
        clear_processed_file(file_path)

    return updated


def clear_terminal_pending_files():
    removed_paths = []
    suppressed_paths = []

    with pending_files_lock:
        remaining_files = []

        for file_info in pending_files:
            if file_info["status"] in CLEARABLE_TERMINAL_STATUSES:
                removed_paths.append(file_info["path"])
                suppressed_paths.extend(file_info.get("generated_paths", []))
            else:
                remaining_files.append(file_info)

        if not removed_paths:
            return 0

        pending_files[:] = remaining_files

    _release_suppressed_generated_paths(suppressed_paths)

    for file_path in removed_paths:
        clear_processed_file(file_path)

    logger.info(f"已清除 {len(removed_paths)} 条终态记录")
    return len(removed_paths)


def retry_failed_files(file_paths=None, stop_event=None):
    retryable_tasks = get_retryable_tasks(file_paths)
    summary = {
        "attempted_count": 0,
        "requeued_count": 0,
        "skipped_count": 0,
    }

    if not retryable_tasks:
        logger.info("当前没有可重试的失败条目")
        return summary

    for task in retryable_tasks:
        if stop_event is not None and stop_event.is_set():
            logger.info("收到停止重试信号，提前结束失败重试")
            break

        file_path = task["path"]
        summary["attempted_count"] += 1
        clear_processed_file(file_path)

        if handle_detected_file(file_path, source="retry"):
            summary["requeued_count"] += 1
        else:
            summary["skipped_count"] += 1

    logger.info(
        "失败条目重试完成: "
        f"尝试 {summary['attempted_count']} 个，"
        f"重新入列 {summary['requeued_count']} 个，"
        f"跳过 {summary['skipped_count']} 个"
    )
    return summary


def _is_file_supported(file_path):
    lower_path = file_path.lower()

    if lower_path.endswith(".ncm"):
        return True

    return lower_path.endswith(SUPPORTED_AUDIO_EXTENSIONS)


def handle_detected_file(file_path, source="watcher"):
    lower_path = file_path.lower()

    if lower_path.endswith(IGNORED_EXTENSIONS):
        return False

    if not _is_file_supported(file_path):
        logger.warning(f"不支持的文件格式: {file_path}")
        return False

    if _is_suppressed_generated_path(file_path):
        logger.info(f"忽略 NCM 解码产物监听事件: {file_path}")
        return False

    if has_processed_file(file_path):
        logger.warning(f"重复文件，已跳过: {file_path}")
        return False

    if not add_pending_file(file_path, status=READING_STATUS):
        return False

    if not mark_processed_file(file_path):
        logger.warning(f"重复文件，已跳过: {file_path}")
        return False

    logger.info(f"检测到文件并已入列: {file_path} - 来源: {source} - 状态: {READING_STATUS}")

    is_ready, reason = _wait_for_file_ready(file_path)

    if not is_ready:
        if reason == "removed":
            clear_processed_file(file_path)
            return False

        _mark_failed_if_present(
            file_path,
            f"文件读取失败: {file_path} - 原因: {reason}"
        )
        return False

    if not has_pending_file(file_path):
        clear_processed_file(file_path)
        logger.info(f"条目已从列表移除，停止后续处理: {file_path}")
        return False

    if lower_path.endswith(".ncm"):
        if not set_pending_file_status(file_path, PROCESSING_STATUS):
            clear_processed_file(file_path)
            return False

        logger.info(f"NCM 读取完成，开始解码: {file_path}")
        _handle_ncm_file(file_path)
        return True

    if set_pending_file_status(file_path, WAITING_STATUS):
        logger.info(f"文件读取完成，等待处理: {file_path}")
        return True

    clear_processed_file(file_path)
    return False


def _wait_for_file_ready(file_path):
    stable_hits = 0
    last_size = None

    for _ in range(FILE_READY_MAX_CHECKS):
        if not has_pending_file(file_path):
            logger.info(f"条目已从列表移除，停止读取检查: {file_path}")
            return False, "removed"

        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return False, "missing"

        try:
            current_size = os.path.getsize(file_path)
        except OSError as e:
            logger.warning(f"读取文件大小失败: {file_path} - {e}")
            return False, "error"

        if last_size is not None and current_size == last_size:
            stable_hits += 1
        else:
            stable_hits = 0

        if stable_hits >= FILE_READY_STABLE_HITS:
            return True, "ready"

        last_size = current_size
        time.sleep(FILE_READY_INTERVAL)

    logger.warning(f"文件读取超时，未能稳定: {file_path}")
    return False, "timeout"


def _find_decoded_output(base_name, retries=3, interval=1):
    for _ in range(retries):
        for ext in DECODED_EXTENSIONS:
            decoded_path = base_name + ext

            if os.path.exists(decoded_path):
                return decoded_path

        time.sleep(interval)

    return None


def _is_non_protected_ncm(output_text):
    lowered_text = output_text.lower()
    return any(
        marker in lowered_text
        for marker in NON_PROTECTED_NCM_MARKERS
    )


def _mark_failed_if_present(file_path, message):
    generated_paths = []

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is not None:
            file_info["status"] = FAILED_STATUS
            generated_paths = list(file_info.get("generated_paths", []))

    _release_suppressed_generated_paths(generated_paths)
    logger.error(message)
    clear_processed_file(file_path)


def _handle_ncm_file(file_path):
    try:
        base_name = os.path.splitext(file_path)[0]
        generated_paths = [
            base_name + ext
            for ext in DECODED_EXTENSIONS
        ]

        _register_suppressed_generated_paths(generated_paths)

        if not set_pending_file_runtime_data(
            file_path,
            generated_paths=generated_paths
        ):
            _release_suppressed_generated_paths(generated_paths)
            clear_processed_file(file_path)
            return

        result = subprocess.run(
            [
                NCMDUMP_PATH,
                file_path
            ],
            check=True,
            capture_output=True,
            text=True,
            **_get_hidden_subprocess_kwargs()
        )

        command_output = (
            (result.stdout or "") +
            "\n" +
            (result.stderr or "")
        ).strip()

        if command_output:
            logger.info(f"NCM 解码输出: {command_output}")

        if _is_non_protected_ncm(command_output):
            _mark_failed_if_present(
                file_path,
                f"NCM 不是网易保护文件: {file_path}"
            )
            return

        decoded_path = _find_decoded_output(base_name)

        if decoded_path is None:
            _mark_failed_if_present(
                file_path,
                f"NCM 解码未生成输出文件: {file_path}"
            )
            return

        if not has_pending_file(file_path):
            _release_suppressed_generated_paths(generated_paths)
            clear_processed_file(file_path)
            logger.info(f"NCM 主条目已移除，停止后续转换关联: {file_path}")
            return

        if not set_pending_file_runtime_data(
            file_path,
            decoded_path=decoded_path,
            generated_paths=generated_paths
        ):
            _release_suppressed_generated_paths(generated_paths)
            clear_processed_file(file_path)
            return

        if not set_pending_file_status(file_path, WAITING_STATUS):
            _release_suppressed_generated_paths(generated_paths)
            clear_processed_file(file_path)
            return

        logger.info(f"NCM 解码完成，等待转换: {file_path}")
        logger.info(f"NCM 解码产物已关联到原任务: {decoded_path}")

    except subprocess.CalledProcessError as e:
        command_output = (
            (e.stdout or "") +
            "\n" +
            (e.stderr or "")
        ).strip()

        if command_output:
            logger.error(f"NCM 解码失败输出: {command_output}")

        _mark_failed_if_present(
            file_path,
            f"NCM 解码失败: {e}"
        )

    except Exception as e:
        _mark_failed_if_present(
            file_path,
            f"NCM 解码失败: {e}"
        )


def scan_existing_files(
    watch_folder=None,
    stop_event=None,
    progress_callback=None,
    return_summary=False
):
    current_watch_folder = watch_folder or get_watch_folder()

    if not current_watch_folder:
        logger.error("监听目录为空，无法扫描已有文件")
        return _finish_scan_summary(
            return_summary,
            {
                "total_count": 0,
                "scanned_count": 0,
                "queued_count": 0,
                "skipped_count": 0,
                "current_file": "",
            }
        )

    if not os.path.isdir(current_watch_folder):
        logger.error(f"监听目录不存在，无法扫描已有文件: {current_watch_folder}")
        return _finish_scan_summary(
            return_summary,
            {
                "total_count": 0,
                "scanned_count": 0,
                "queued_count": 0,
                "skipped_count": 0,
                "current_file": "",
            }
        )

    summary = {
        "total_count": 0,
        "scanned_count": 0,
        "queued_count": 0,
        "skipped_count": 0,
        "current_file": "",
    }

    logger.info(f"开始扫描已有文件: {current_watch_folder}")

    try:
        entries = sorted(
            [
                entry
                for entry in os.scandir(current_watch_folder)
                if entry.is_file()
            ],
            key=lambda entry: entry.name.lower()
        )
        summary["total_count"] = len(entries)

        for entry in entries:
            if stop_event is not None and stop_event.is_set():
                logger.info("收到停止扫描信号，提前结束已有文件扫描")
                break

            summary["scanned_count"] += 1
            summary["current_file"] = entry.name

            if handle_detected_file(entry.path, source="scan"):
                summary["queued_count"] += 1
            else:
                summary["skipped_count"] += 1

            if progress_callback is not None:
                progress_callback(summary.copy())

    except Exception as e:
        logger.error(f"扫描已有文件失败: {e}")
        return _finish_scan_summary(return_summary, summary)

    logger.info(
        "已有文件扫描完成: "
        f"扫描 {summary['scanned_count']}/{summary['total_count']} 个，"
        f"新增入列 {summary['queued_count']} 个，"
        f"跳过 {summary['skipped_count']} 个"
    )
    return _finish_scan_summary(return_summary, summary)


def _finish_scan_summary(return_summary, summary):
    if return_summary:
        return summary

    return summary["queued_count"]


class MyHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        handle_detected_file(event.src_path, source="watcher")

    def _handle_ncm_file(self, file_path):
        _handle_ncm_file(file_path)


def start_watch(stop_event=None, watch_folder=None):
    """
    兼容旧调用方式：
    - start_watch()
    - start_watch(stop_event=event)
    - start_watch(stop_event=event, watch_folder=folder)

    stop_event:
        传入 threading.Event 后，可由外部优雅停止监听。
    watch_folder:
        显式指定监听目录；如果不传，则动态读取当前配置。
    """
    current_watch_folder = watch_folder or get_watch_folder()

    if not current_watch_folder:
        logger.error("监听目录为空，无法启动监听")
        return

    if not os.path.isdir(current_watch_folder):
        logger.error(f"监听目录不存在，无法启动监听: {current_watch_folder}")
        return

    observer = Observer()
    handler = MyHandler()

    try:
        observer.schedule(
            handler,
            current_watch_folder,
            recursive=False
        )

        observer.start()
        logger.info(f"开始监听文件夹: {current_watch_folder}")

        while True:
            if stop_event is not None and stop_event.is_set():
                logger.info("收到停止监听信号，准备退出 watcher")
                break

            time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("收到 KeyboardInterrupt，停止 watcher")

    except Exception as e:
        logger.error(f"监听器运行失败: {e}")

    finally:
        if observer.is_alive():
            observer.stop()

        observer.join()
        logger.info("watcher 已停止")

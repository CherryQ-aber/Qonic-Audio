# 监听文件夹，处理新文件
import os
import shutil
import subprocess
import threading
import time
import uuid

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import (
    NCMDUMP_PATH,
    NCM_TEMP_DIR,
    get_cache_folder,
    get_output_folder,
    get_temp_folder,
    get_watch_folder,
)
from formats import (
    get_source_format,
    is_ignored_file,
    is_supported_input_file,
    is_supported_target_format,
    normalize_target_format,
)
from logger import logger

DECODED_EXTENSIONS = (
    ".mp3",
    ".flac",
    ".wav"
)

QUEUED_STATUS = "已入队"
READING_STATUS = "读取中"
WAITING_STATUS = "等待处理"
PROCESSING_STATUS = "处理中"
COMPLETED_STATUS = "已完成"
FAILED_STATUS = "失败"
SKIPPED_STATUS = "已跳过"
CANCELLED_STATUS = "已取消"

DETECTED_FILE_ADDED = "added"
DETECTED_FILE_DUPLICATE = "duplicate"
DETECTED_FILE_IGNORED = "ignored"
DETECTED_FILE_UNSUPPORTED = "unsupported"
DETECTED_FILE_SUPPRESSED = "suppressed"
DETECTED_FILE_OUTPUT_PATH = "output_path"
DETECTED_FILE_RUNTIME_PATH = "runtime_path"

# Explicit user actions may intentionally use an existing output tree as input.
# Automatic discovery must still reject it to prevent converted files feeding
# back into the watcher.
OUTPUT_ROOT_ALLOWED_SOURCES = frozenset(
    {
        "qml_file",
        "qml_drop",
        "qml_scan",
        "folder_browser",
        "manual_drop",
        "retry",
    }
)

TERMINAL_STATUSES = (
    COMPLETED_STATUS,
    FAILED_STATUS,
    SKIPPED_STATUS,
    CANCELLED_STATUS,
)

CLEARABLE_TERMINAL_STATUSES = (
    COMPLETED_STATUS,
    FAILED_STATUS,
    CANCELLED_STATUS,
)

PREPARE_STATUSES = (
    QUEUED_STATUS,
    READING_STATUS,
)

STATUS_DISPLAY = {
    QUEUED_STATUS: {
        "label": "已入队",
        "detail": "等待后台读取验证",
        "color": "#6C7A89",
    },
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
    CANCELLED_STATUS: {
        "label": "已取消",
        "detail": "用户已取消本次处理",
        "color": "#828282",
    },
}

NON_PROTECTED_NCM_MARKERS = (
    "not netease protected file",
)

FILE_READY_MAX_CHECKS = 12
FILE_READY_INTERVAL = 1
FILE_READY_STABLE_HITS = 2
QUEUE_PREPARE_IDLE_INTERVAL = 0.5

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
RUNTIME_UNSET = object()


def _normalize_file_path(file_path):
    return os.path.normpath(os.path.abspath(os.fspath(file_path)))


def get_status_display(status):
    fallback = {
        "label": status,
        "detail": "未知状态",
        "color": "#828282",
    }

    return STATUS_DISPLAY.get(status, fallback).copy()


def _build_pending_file(file_path, status, task_snapshot=None):
    snapshot = dict(task_snapshot or {})
    snapshot_target_format = normalize_target_format(snapshot.get("target_format"))
    if "target_format_override" in snapshot:
        target_format_override = normalize_target_format(
            snapshot.get("target_format_override")
        )
    else:
        # Older callers used ``target_format`` as the file-level override.
        target_format_override = snapshot_target_format

    if "output_directory_override" in snapshot:
        output_directory_override = str(
            snapshot.get("output_directory_override") or ""
        )
    else:
        # Preserve the pre-5.9.2 task snapshot contract for legacy callers.
        output_directory_override = str(snapshot.get("output_directory") or "")

    return {
        "path": file_path,
        "filename": os.path.basename(file_path),
        "format": get_source_format(file_path),
        "status": status,
        "target_format": snapshot_target_format,
        "target_format_override": target_format_override,
        "enabled_for_run": bool(snapshot.get("enabled_for_run", True)),
        "decoded_path": None,
        "generated_paths": [],
        "temp_work_dir": None,
        "temp_ncm_path": None,
        # Queue parameters are copied when the task is created.  Later QML
        # settings edits therefore affect only newly added files.
        "source_type": str(snapshot.get("source_type") or get_source_format(file_path)),
        "source_action": str(snapshot.get("source_action") or "保留源文件"),
        "output_directory": str(snapshot.get("output_directory") or ""),
        "output_directory_override": output_directory_override,
        "relative_output_path": str(snapshot.get("relative_output_path") or ""),
        "preserve_relative_structure": bool(snapshot.get("preserve_relative_structure", False)),
        "request_generation": int(snapshot.get("request_generation") or 0),
        "created_at": str(snapshot.get("created_at") or ""),
        "source_root": str(snapshot.get("source_root") or ""),
        "source": str(snapshot.get("source") or "watcher"),
        "create_format_subfolder": snapshot.get("create_format_subfolder"),
        "stage": str(snapshot.get("stage") or "等待读取验证"),
        "output_path": "",
        "error_summary": "",
        "lyrics_result": {},
    }


def _find_pending_file_unlocked(file_path):
    identity = os.path.normcase(_normalize_file_path(file_path))
    for file_info in pending_files:
        if os.path.normcase(_normalize_file_path(file_info["path"])) == identity:
            return file_info

    return None


def _refresh_pending_file_unlocked(file_info, file_path, status, task_snapshot=None):
    refreshed = _build_pending_file(file_path, status, task_snapshot)
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


def add_pending_file(file_path, status=WAITING_STATUS, task_snapshot=None):
    new_file_info = _build_pending_file(file_path, status, task_snapshot)
    runtime_cleanup_data = None
    refreshed_existing = False

    with pending_files_lock:
        existing_file_info = _find_pending_file_unlocked(file_path)

        if existing_file_info is not None:
            if existing_file_info["status"] in TERMINAL_STATUSES:
                runtime_cleanup_data = _build_runtime_cleanup_data(existing_file_info)
                _refresh_pending_file_unlocked(
                    existing_file_info,
                    file_path,
                    status,
                    task_snapshot,
                )
                refreshed_existing = True
            else:
                logger.warning(f"文件已在待处理列表中，跳过重复加入: {file_path}")
                return False

        else:
            pending_files.append(new_file_info)

    if runtime_cleanup_data is not None:
        _cleanup_runtime_data(runtime_cleanup_data)

    if refreshed_existing:
        logger.info(f"文件重新加入待处理列表: {file_path}")
        return True

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


def set_pending_file_runtime_data(
    file_path,
    decoded_path=RUNTIME_UNSET,
    generated_paths=RUNTIME_UNSET,
    temp_work_dir=RUNTIME_UNSET,
    temp_ncm_path=RUNTIME_UNSET,
    stage=RUNTIME_UNSET,
    output_path=RUNTIME_UNSET,
    error_summary=RUNTIME_UNSET,
    lyrics_result=RUNTIME_UNSET,
):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法更新运行时数据: {file_path}")
            return False

        if decoded_path is not RUNTIME_UNSET:
            file_info["decoded_path"] = decoded_path

        if generated_paths is not RUNTIME_UNSET:
            file_info["generated_paths"] = list(generated_paths or [])

        if temp_work_dir is not RUNTIME_UNSET:
            file_info["temp_work_dir"] = temp_work_dir

        if temp_ncm_path is not RUNTIME_UNSET:
            file_info["temp_ncm_path"] = temp_ncm_path

        if stage is not RUNTIME_UNSET:
            file_info["stage"] = str(stage or "")

        if output_path is not RUNTIME_UNSET:
            file_info["output_path"] = str(output_path or "")

        if error_summary is not RUNTIME_UNSET:
            file_info["error_summary"] = str(error_summary or "")

        if lyrics_result is not RUNTIME_UNSET:
            file_info["lyrics_result"] = dict(lyrics_result or {})

    return True


def _build_runtime_cleanup_data(file_info):
    return {
        "path": file_info.get("path"),
        "decoded_path": file_info.get("decoded_path"),
        "generated_paths": list(file_info.get("generated_paths") or []),
        "temp_work_dir": file_info.get("temp_work_dir"),
        "temp_ncm_path": file_info.get("temp_ncm_path"),
    }


def _is_path_in_ncm_temp(path):
    if not path:
        return False

    try:
        root = os.path.normcase(os.path.abspath(NCM_TEMP_DIR))
        target = os.path.normcase(os.path.abspath(path))
        return os.path.commonpath([root, target]) == root and target != root
    except (OSError, ValueError):
        return False


def _cleanup_runtime_data(runtime_data):
    if not runtime_data:
        return False

    cleaned = False
    generated_paths = runtime_data.get("generated_paths") or []
    temp_work_dir = runtime_data.get("temp_work_dir")

    _release_suppressed_generated_paths(generated_paths)

    if temp_work_dir:
        if not _is_path_in_ncm_temp(temp_work_dir):
            logger.warning(f"拒绝清理非 NCM 临时目录: {temp_work_dir}")
            return False

        if os.path.isdir(temp_work_dir):
            try:
                shutil.rmtree(temp_work_dir)
                logger.info(f"NCM 临时文件已清理: {temp_work_dir}")
                return True
            except OSError as e:
                logger.warning(f"NCM 临时目录清理失败: {temp_work_dir} - {e}")
                return False

        return False

    cleanup_paths = list(generated_paths)

    for key in ("decoded_path", "temp_ncm_path"):
        value = runtime_data.get(key)
        if value:
            cleanup_paths.append(value)

    for cleanup_path in cleanup_paths:
        if not _is_path_in_ncm_temp(cleanup_path):
            continue

        if not os.path.isfile(cleanup_path):
            continue

        try:
            os.remove(cleanup_path)
            logger.info(f"NCM 临时文件已清理: {cleanup_path}")
            cleaned = True
        except OSError as e:
            logger.warning(f"NCM 临时文件清理失败: {cleanup_path} - {e}")

    return cleaned


def cleanup_task_runtime_files(file_path):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            return False

        runtime_data = _build_runtime_cleanup_data(file_info)

    cleaned = _cleanup_runtime_data(runtime_data)

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is not None:
            file_info["decoded_path"] = None
            file_info["generated_paths"] = []
            file_info["temp_work_dir"] = None
            file_info["temp_ncm_path"] = None

    return cleaned


def set_pending_file_target_format(file_path, target_format):
    file_path = _normalize_file_path(file_path)
    normalized_format = None

    if target_format:
        normalized_format = normalize_target_format(target_format)

        if not is_supported_target_format(normalized_format):
            logger.warning(f"不支持的目标格式，已忽略: {target_format}")
            return False

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法设置目标格式: {file_path}")
            return False

        if not _can_modify_task_policy(file_info["status"]):
            logger.warning(f"当前状态不允许修改目标格式: {file_path}")
            return False

        file_info["target_format"] = normalized_format
        file_info["target_format_override"] = normalized_format
        if file_info.get("source_type"):
            file_info["stage"] = "等待处理"

    if normalized_format:
        logger.info(f"单文件目标格式已设置: {file_path} -> {normalized_format}")
    else:
        logger.info(f"单文件目标格式已恢复为跟随全局: {file_path}")

    return True


def _can_modify_task_policy(status):
    return status not in (
        READING_STATUS,
        PROCESSING_STATUS,
        COMPLETED_STATUS,
    )


def set_pending_file_enabled_for_run(file_path, enabled):
    file_path = _normalize_file_path(file_path)
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法修改参与策略: {file_path}")
            return False

        if not _can_modify_task_policy(file_info["status"]):
            logger.warning(f"当前状态不允许修改参与策略: {file_path}")
            return False

        file_info["enabled_for_run"] = bool(enabled)

    logger.info(
        f"任务参与策略已更新: {file_path} -> "
        f"{'参与本轮转换' if enabled else '本轮跳过'}"
    )
    return True


def set_pending_file_output_directory_override(file_path, output_directory):
    file_path = _normalize_file_path(file_path)
    normalized_directory = ""
    if output_directory:
        normalized_directory = os.path.normpath(
            os.path.abspath(os.fspath(output_directory))
        )
        if not os.path.isdir(normalized_directory):
            logger.warning(f"任务级输出目录不存在，已拒绝: {normalized_directory}")
            return False

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            logger.warning(f"待处理文件不存在，无法修改输出目录: {file_path}")
            return False

        if not _can_modify_task_policy(file_info["status"]):
            logger.warning(f"当前状态不允许修改输出目录: {file_path}")
            return False

        file_info["output_directory_override"] = normalized_directory

    logger.info(
        f"任务级输出目录已更新: {file_path} -> "
        f"{normalized_directory or '跟随默认输出目录'}"
    )
    return True


def remove_pending_file_by_path(file_path):
    file_path = _normalize_file_path(file_path)
    runtime_cleanup_data = None

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            return False

        runtime_cleanup_data = _build_runtime_cleanup_data(file_info)
        pending_files.remove(file_info)

    _cleanup_runtime_data(runtime_cleanup_data)
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
    task["lyrics_result"] = dict(task.get("lyrics_result") or {})
    input_path = task.get("decoded_path") or task["path"]

    task["input_path"] = input_path
    task["is_ncm_task"] = bool(task.get("decoded_path"))
    task["target_format"] = task.get("target_format")
    task["target_format_override"] = task.get("target_format_override")
    task["enabled_for_run"] = bool(task.get("enabled_for_run", True))
    task["output_directory_override"] = str(
        task.get("output_directory_override") or ""
    )
    task["can_convert"] = task["status"] == WAITING_STATUS
    task["can_convert_in_batch"] = (
        task["can_convert"] and task["enabled_for_run"]
    )
    task["can_retry"] = task["status"] == FAILED_STATUS
    task["can_change_target_format"] = _can_modify_task_policy(task["status"])
    task["can_change_run_policy"] = _can_modify_task_policy(task["status"])
    task["can_change_output_directory"] = _can_modify_task_policy(task["status"])

    return task


def get_task_snapshots():
    with pending_files_lock:
        return [
            _build_task_snapshot(file_info)
            for file_info in pending_files
        ]


def get_convertible_tasks(include_disabled=False):
    return [
        task
        for task in get_task_snapshots()
        if task["can_convert"]
        and (include_disabled or task["enabled_for_run"])
    ]


def claim_pending_file_for_conversion(file_path, include_disabled=False):
    """Atomically claim a waiting task so two dispatches cannot start it."""
    file_path = _normalize_file_path(file_path)
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)
        if file_info is None or file_info["status"] != WAITING_STATUS:
            return False
        if not include_disabled and not bool(file_info.get("enabled_for_run", True)):
            return False
        file_info["status"] = PROCESSING_STATUS
    return True


def has_preparing_tasks():
    with pending_files_lock:
        return any(
            file_info["status"] in PREPARE_STATUSES
            for file_info in pending_files
        )


def get_retryable_tasks(file_paths=None):
    selected_paths = {
        os.path.normcase(_normalize_file_path(file_path))
        for file_path in (file_paths or [])
    }

    return [
        task
        for task in get_task_snapshots()
        if task["can_retry"]
        and (
            not selected_paths
            or os.path.normcase(task["path"]) in selected_paths
        )
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
    runtime_cleanup_items = []

    with pending_files_lock:
        remaining_files = []

        for file_info in pending_files:
            if file_info["status"] in CLEARABLE_TERMINAL_STATUSES:
                removed_paths.append(file_info["path"])
                runtime_cleanup_items.append(
                    _build_runtime_cleanup_data(file_info)
                )
            else:
                remaining_files.append(file_info)

        if not removed_paths:
            return 0

        pending_files[:] = remaining_files

    for runtime_cleanup_data in runtime_cleanup_items:
        _cleanup_runtime_data(runtime_cleanup_data)

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
        snapshot = {
            key: task.get(key)
            for key in (
                "source_type",
                "source_action",
                "output_directory",
                "relative_output_path",
                "preserve_relative_structure",
                "request_generation",
                "created_at",
                "source_root",
                "create_format_subfolder",
                "target_format",
                "target_format_override",
                "output_directory_override",
                "enabled_for_run",
            )
        }

        if handle_detected_file(file_path, source="retry", task_snapshot=snapshot):
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
    return is_supported_input_file(file_path)


def _enqueue_result(added, reason):
    return {
        "added": bool(added),
        "reason": str(reason),
    }


def handle_detected_file_with_reason(
    file_path,
    source="watcher",
    task_snapshot=None,
):
    file_path = _normalize_file_path(file_path)

    if is_ignored_file(file_path):
        logger.info(f"忽略非音频辅助文件: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_IGNORED)

    if not _is_file_supported(file_path):
        logger.warning(f"不支持的文件格式: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_UNSUPPORTED)

    if _is_suppressed_generated_path(file_path):
        logger.info(f"忽略 NCM 解码产物监听事件: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_SUPPRESSED)

    if _is_runtime_path(file_path):
        logger.info(f"忽略程序运行时文件: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_RUNTIME_PATH)

    if (
        _is_output_path(file_path)
        and _normalize_source(source) not in OUTPUT_ROOT_ALLOWED_SOURCES
    ):
        logger.info(f"忽略程序输出文件: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_OUTPUT_PATH)

    if has_processed_file(file_path):
        logger.warning(f"重复文件，已跳过: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_DUPLICATE)

    snapshot = dict(task_snapshot or {})
    snapshot.setdefault("source_type", get_source_format(file_path))
    snapshot.setdefault("source_action", "保留源文件")
    snapshot.setdefault("stage", "等待读取验证")
    snapshot.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    snapshot.setdefault("source", source)

    if not add_pending_file(file_path, status=QUEUED_STATUS, task_snapshot=snapshot):
        return _enqueue_result(False, DETECTED_FILE_DUPLICATE)

    if not mark_processed_file(file_path):
        logger.warning(f"重复文件，已跳过: {file_path}")
        return _enqueue_result(False, DETECTED_FILE_DUPLICATE)

    logger.info(f"检测到文件并已入队: {file_path} - 来源: {source} - 状态: {QUEUED_STATUS}")
    return _enqueue_result(True, DETECTED_FILE_ADDED)


def handle_detected_file(file_path, source="watcher", task_snapshot=None):
    """Compatibility wrapper for callers that only need success or failure."""
    result = handle_detected_file_with_reason(
        file_path,
        source=source,
        task_snapshot=task_snapshot,
    )
    return bool(result["added"])


def _normalize_source(source):
    return str(source or "watcher").strip().lower()


def _is_path_within_root(file_path, root):
    if not root:
        return False

    try:
        normalized_root = os.path.normcase(os.path.abspath(root))
        normalized_path = os.path.normcase(os.path.abspath(file_path))
        return os.path.commonpath([normalized_root, normalized_path]) == normalized_root
    except (OSError, ValueError):
        return False


def _is_output_path(file_path):
    return _is_path_within_root(file_path, get_output_folder())


def _is_runtime_path(file_path):
    return any(
        _is_path_within_root(file_path, root)
        for root in (get_temp_folder(), get_cache_folder())
    )


def _is_generated_output_or_runtime_path(file_path):
    """Prevent QML watcher runs from re-enqueueing outputs and cache files."""
    return _is_output_path(file_path) or _is_runtime_path(file_path)


def _get_prepare_task_paths():
    with pending_files_lock:
        return [
            file_info["path"]
            for file_info in pending_files
            if file_info["status"] in PREPARE_STATUSES
        ]


def _claim_pending_file_for_prepare(file_path):
    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is None:
            return False

        if file_info["status"] not in PREPARE_STATUSES:
            return False

        file_info["status"] = READING_STATUS

    return True


def _prepare_single_pending_file(file_path, stop_event=None):
    if not _claim_pending_file_for_prepare(file_path):
        return False

    set_pending_file_runtime_data(file_path, stage="正在验证文件稳定性")

    lower_path = file_path.lower()
    is_ready, reason = _wait_for_file_ready(file_path, stop_event=stop_event)

    if not is_ready:
        if reason == "removed":
            clear_processed_file(file_path)
            return False

        if reason == "stopped":
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

        set_pending_file_runtime_data(file_path, stage="正在解码 NCM")
        logger.info(f"NCM 读取完成，开始解码: {file_path}")
        _handle_ncm_file(file_path)
        return True

    if set_pending_file_status(file_path, WAITING_STATUS):
        set_pending_file_runtime_data(file_path, stage="等待批量转换")
        logger.info(f"文件读取完成，等待处理: {file_path}")
        return True

    clear_processed_file(file_path)
    return False


def prepare_pending_files(
    stop_event=None,
    keep_running=False,
    idle_interval=QUEUE_PREPARE_IDLE_INTERVAL,
):
    summary = {
        "processed_count": 0,
        "idle_count": 0,
    }

    logger.info("后台读取/验证线程已启动")

    while True:
        if stop_event is not None and stop_event.is_set():
            break

        task_paths = _get_prepare_task_paths()

        if not task_paths:
            summary["idle_count"] += 1

            if not keep_running:
                break

            if stop_event is not None:
                stop_event.wait(idle_interval)
            else:
                time.sleep(idle_interval)

            continue

        for file_path in task_paths:
            if stop_event is not None and stop_event.is_set():
                break

            if _prepare_single_pending_file(file_path, stop_event=stop_event):
                summary["processed_count"] += 1

        if not keep_running:
            break

    logger.info("后台读取/验证线程已停止")
    return summary


def _wait_for_file_ready(file_path, stop_event=None):
    stable_hits = 0
    last_size = None

    for _ in range(FILE_READY_MAX_CHECKS):
        if stop_event is not None and stop_event.is_set():
            logger.info(f"收到停止读取验证信号: {file_path}")
            return False, "stopped"

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
        if stop_event is not None:
            stop_event.wait(FILE_READY_INTERVAL)
        else:
            time.sleep(FILE_READY_INTERVAL)

    logger.warning(f"文件读取超时，未能稳定: {file_path}")
    return False, "timeout"


def _create_ncm_temp_work_dir():
    os.makedirs(NCM_TEMP_DIR, exist_ok=True)
    temp_work_dir = os.path.join(NCM_TEMP_DIR, uuid.uuid4().hex)
    os.makedirs(temp_work_dir, exist_ok=False)
    logger.info(f"NCM 临时工作目录: {temp_work_dir}")
    return temp_work_dir


def _list_ncm_temp_files(temp_work_dir):
    if not temp_work_dir or not os.path.isdir(temp_work_dir):
        return []

    return [
        os.path.join(temp_work_dir, name)
        for name in os.listdir(temp_work_dir)
        if os.path.isfile(os.path.join(temp_work_dir, name))
    ]


def _find_decoded_output_in_temp(temp_work_dir, temp_ncm_path, retries=3, interval=1):
    expected_base_name = os.path.splitext(temp_ncm_path)[0]

    for _ in range(retries):
        for ext in DECODED_EXTENSIONS:
            decoded_path = expected_base_name + ext

            if os.path.exists(decoded_path):
                return decoded_path

        candidates = [
            path
            for path in _list_ncm_temp_files(temp_work_dir)
            if path.lower().endswith(DECODED_EXTENSIONS)
        ]

        if candidates:
            return max(
                candidates,
                key=lambda path: (
                    os.path.getmtime(path),
                    os.path.getsize(path),
                )
            )

        time.sleep(interval)

    return None


def _is_non_protected_ncm(output_text):
    lowered_text = output_text.lower()
    return any(
        marker in lowered_text
        for marker in NON_PROTECTED_NCM_MARKERS
    )


def _mark_failed_if_present(file_path, message):
    runtime_cleanup_data = None

    with pending_files_lock:
        file_info = _find_pending_file_unlocked(file_path)

        if file_info is not None:
            file_info["status"] = FAILED_STATUS
            file_info["stage"] = "处理失败"
            file_info["error_summary"] = message
            runtime_cleanup_data = _build_runtime_cleanup_data(file_info)

    if runtime_cleanup_data is not None:
        cleanup_task_runtime_files(file_path)

    logger.error(message)
    clear_processed_file(file_path)


def _handle_ncm_file(file_path):
    temp_work_dir = None
    temp_ncm_path = None

    try:
        temp_work_dir = _create_ncm_temp_work_dir()
        temp_ncm_path = os.path.join(
            temp_work_dir,
            os.path.basename(file_path)
        )
        shutil.copy2(file_path, temp_ncm_path)
        logger.info(f"NCM 已复制到临时目录: {temp_ncm_path}")

        generated_paths = [temp_ncm_path]

        if not set_pending_file_runtime_data(
            file_path,
            generated_paths=generated_paths,
            temp_work_dir=temp_work_dir,
            temp_ncm_path=temp_ncm_path,
        ):
            _cleanup_runtime_data({
                "generated_paths": generated_paths,
                "temp_work_dir": temp_work_dir,
                "temp_ncm_path": temp_ncm_path,
            })
            clear_processed_file(file_path)
            return

        logger.info(f"NCM 将在临时目录中执行 ncmdump: {temp_work_dir}")
        result = subprocess.run(
            [
                NCMDUMP_PATH,
                temp_ncm_path
            ],
            cwd=temp_work_dir,
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

        decoded_path = _find_decoded_output_in_temp(
            temp_work_dir,
            temp_ncm_path
        )

        if decoded_path is None:
            _mark_failed_if_present(
                file_path,
                f"NCM 解码未生成输出文件: {file_path}"
            )
            return

        generated_paths = _list_ncm_temp_files(temp_work_dir)
        if decoded_path not in generated_paths:
            generated_paths.append(decoded_path)

        logger.info(f"NCM 解码产物已生成于临时目录: {decoded_path}")

        if not has_pending_file(file_path):
            _cleanup_runtime_data({
                "generated_paths": generated_paths,
                "temp_work_dir": temp_work_dir,
                "temp_ncm_path": temp_ncm_path,
                "decoded_path": decoded_path,
            })
            clear_processed_file(file_path)
            logger.info(f"NCM 主条目已移除，停止后续转换关联: {file_path}")
            return

        if not set_pending_file_runtime_data(
            file_path,
            decoded_path=decoded_path,
            generated_paths=generated_paths,
            temp_work_dir=temp_work_dir,
            temp_ncm_path=temp_ncm_path,
        ):
            _cleanup_runtime_data({
                "generated_paths": generated_paths,
                "temp_work_dir": temp_work_dir,
                "temp_ncm_path": temp_ncm_path,
                "decoded_path": decoded_path,
            })
            clear_processed_file(file_path)
            return

        if not set_pending_file_status(file_path, WAITING_STATUS):
            _cleanup_runtime_data({
                "generated_paths": generated_paths,
                "temp_work_dir": temp_work_dir,
                "temp_ncm_path": temp_ncm_path,
                "decoded_path": decoded_path,
            })
            clear_processed_file(file_path)
            return

        set_pending_file_runtime_data(file_path, stage="NCM 解码完成，等待批量转换")

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
        if temp_work_dir and os.path.isdir(temp_work_dir):
            _cleanup_runtime_data({
                "generated_paths": _list_ncm_temp_files(temp_work_dir),
                "temp_work_dir": temp_work_dir,
                "temp_ncm_path": temp_ncm_path,
            })

    except Exception as e:
        _mark_failed_if_present(
            file_path,
            f"NCM 解码失败: {e}"
        )
        if temp_work_dir and os.path.isdir(temp_work_dir):
            _cleanup_runtime_data({
                "generated_paths": _list_ncm_temp_files(temp_work_dir),
                "temp_work_dir": temp_work_dir,
                "temp_ncm_path": temp_ncm_path,
            })


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
    logger.info("已有文件扫描完成仅代表入队完成，后台读取/验证仍会继续")
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

"""Safe local-path extraction for QML drag-and-drop payloads.

QML hands ``DropArea`` URLs to Python as ``QUrl`` instances on Windows.  The
workspace must accept only local filesystem paths; web and UNC-style
network URLs are deliberately ignored before any queue work begins.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

from PySide6.QtCore import QUrl


def extract_local_drop_paths(values: object) -> tuple[list[str], list[str]]:
    """Return normalized local paths and user-readable skip reasons.

    ``QUrl.toLocalFile()`` performs the required percent decoding, including
    Windows paths containing spaces, ``#``, ``%`` and non-ASCII characters.
    Raw local paths are accepted for bridge tests and native integrations, but
    URLs with a non-local scheme or a network host never become queue inputs.
    """

    if values is None:
        return [], []

    if isinstance(values, (str, bytes, QUrl)):
        items: Iterable[object] = [values]
    else:
        try:
            items = list(values)  # type: ignore[arg-type]
        except TypeError:
            return [], ["拖入数据无法识别"]

    paths: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()

    for item in items:
        path, reason = _extract_local_path(item)
        if not path:
            skipped.append(reason or "不是本地文件或文件夹")
            continue

        normalized = os.path.abspath(os.path.normpath(path))
        identity = os.path.normcase(normalized)
        if identity in seen:
            continue
        seen.add(identity)
        paths.append(normalized)

    return paths, skipped


def _extract_local_path(value: object) -> tuple[str, str]:
    if isinstance(value, QUrl):
        return _from_url(value)

    raw = str(value or "").strip()
    if not raw:
        return "", "空拖入项目"

    # QUrl treats ``C:\...`` as a URL with scheme ``c``.  Recognize native
    # drive paths first, while still rejecting raw UNC/network locations.
    if raw.startswith(("\\\\", "//")):
        return "", "已跳过网络位置"
    if re.match(r"^[A-Za-z]:[\\/]", raw) or os.path.isabs(raw):
        return raw, ""

    url = QUrl(raw)
    if url.isValid() and (url.scheme() or raw.lower().startswith("file:")):
        return _from_url(url)

    # A raw Windows path is not a URL.  Keep it as a local candidate so the
    # caller can return a precise "不存在" / "不支持" result if appropriate.
    return raw, ""


def _from_url(url: QUrl) -> tuple[str, str]:
    if not url.isLocalFile():
        return "", "已跳过非本地 URL"
    if url.host():
        return "", "已跳过网络位置"

    local_path = url.toLocalFile()
    if not local_path:
        return "", "本地 URL 未包含文件路径"
    return local_path, ""

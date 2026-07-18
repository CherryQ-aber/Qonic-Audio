from __future__ import annotations

import re


_LINE_TIMESTAMP_RE = re.compile(r"^\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")
_TIMESTAMP_PRECISIONS = {"centisecond", "millisecond"}


def normalize_timestamp_precision(value: object) -> str:
    normalized = str(value or "millisecond").strip().lower()
    return normalized if normalized in _TIMESTAMP_PRECISIONS else "millisecond"


def format_lrc_timestamp(
    milliseconds: int,
    precision: str = "millisecond",
) -> str:
    """Format a real player position using the selected LRC precision."""
    try:
        normalized = max(0, int(milliseconds))
    except (TypeError, ValueError):
        normalized = 0
    if normalize_timestamp_precision(precision) == "millisecond":
        total_seconds, remaining_milliseconds = divmod(normalized, 1_000)
        minutes, seconds = divmod(total_seconds, 60)
        return (
            f"[{minutes:02d}:{seconds:02d}.{remaining_milliseconds:03d}]"
        )

    # Keep the existing centisecond rounding behavior when that mode is chosen.
    total_centiseconds = max(0, int(round(normalized / 10.0)))
    total_seconds, centiseconds = divmod(total_centiseconds, 100)
    minutes, seconds = divmod(total_seconds, 60)
    return f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]"


def apply_lrc_timestamp(
    text: str,
    *,
    selection_start: int,
    selection_end: int,
    cursor_position: int,
    milliseconds: int,
    precision: str = "millisecond",
) -> dict[str, object]:
    """Insert or replace the first timestamp on the selected/cursor line."""
    source = str(text or "")
    text_length = len(source)

    def clamp(position: int) -> int:
        try:
            value = int(position)
        except (TypeError, ValueError):
            value = 0
        return max(0, min(value, text_length))

    safe_selection_start = clamp(selection_start)
    safe_selection_end = clamp(selection_end)
    if safe_selection_start > safe_selection_end:
        safe_selection_start, safe_selection_end = (
            safe_selection_end,
            safe_selection_start,
        )
    safe_cursor = clamp(cursor_position)
    target_position = (
        safe_selection_start
        if safe_selection_start != safe_selection_end
        else safe_cursor
    )

    line_start = max(
        source.rfind("\n", 0, target_position),
        source.rfind("\r", 0, target_position),
    ) + 1
    line_end_candidates = [
        position
        for position in (
            source.find("\r", line_start),
            source.find("\n", line_start),
        )
        if position >= 0
    ]
    line_end = min(line_end_candidates) if line_end_candidates else text_length
    line_text = source[line_start:line_end]
    timestamp_match = _LINE_TIMESTAMP_RE.match(line_text)
    replaced_end = line_start + (
        timestamp_match.end() if timestamp_match is not None else 0
    )
    timestamp = format_lrc_timestamp(milliseconds, precision)
    updated = source[:line_start] + timestamp + source[replaced_end:]
    delta = len(timestamp) - (replaced_end - line_start)
    updated_length = len(updated)

    def shift(position: int) -> int:
        if position < line_start:
            shifted = position
        elif position < replaced_end:
            shifted = line_start + len(timestamp)
        else:
            shifted = position + delta
        return max(0, min(shifted, updated_length))

    return {
        "text": updated,
        "timestamp": timestamp,
        "changed": updated != source,
        "line_start": line_start,
        "selection_start": shift(safe_selection_start),
        "selection_end": shift(safe_selection_end),
        "cursor_position": shift(safe_cursor),
    }

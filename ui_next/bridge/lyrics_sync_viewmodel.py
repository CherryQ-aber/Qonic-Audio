from __future__ import annotations

from bisect import bisect_right
import re

from PySide6.QtCore import Property, Signal, Slot

from ui_next.bridge.base_viewmodel import BaseViewModel


class LyricsSyncViewModel(BaseViewModel):
    """Project the current lyrics draft onto the single global player clock."""

    linesChanged = Signal()
    playbackLineChanged = Signal()
    availabilityChanged = Signal()
    followEnabledChanged = Signal()

    _TIMED_LINE_RE = re.compile(
        r"^\s*((?:\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\])+)[ \t]*(.*)$"
    )
    _TIMESTAMP_RE = re.compile(
        r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]"
    )

    def __init__(self, edit_session, audio_player) -> None:
        super().__init__()
        self._edit_session = edit_session
        self._audio_player = audio_player
        self._lyrics_text = ""
        self._lines: list[dict[str, object]] = []
        self._timeline: list[tuple[int, int]] = []
        self._timeline_positions: list[int] = []
        self._position = max(0, int(getattr(audio_player, "position", 0)))
        self._current_line_index = -1
        self._available_for_playback = False
        self._follow_enabled = True

        edit_session.stateChanged.connect(self._on_lyrics_state_changed)
        audio_player.stateChanged.connect(self._on_player_state_changed)
        self._reload_lyrics(force=True)

    @Property("QVariantList", notify=linesChanged)
    def lines(self) -> list[dict[str, object]]:
        return [dict(line) for line in self._lines]

    @Property(int, notify=linesChanged)
    def lineCount(self) -> int:
        return len(self._lines)

    @Property(bool, notify=linesChanged)
    def hasTimedLyrics(self) -> bool:
        return bool(self._timeline)

    @Property(int, notify=playbackLineChanged)
    def currentLineIndex(self) -> int:
        return self._current_line_index

    @Property(str, notify=playbackLineChanged)
    def currentLineText(self) -> str:
        return self._line_value(self._current_line_index, "text")

    @Property(str, notify=playbackLineChanged)
    def currentLineTranslation(self) -> str:
        return self._line_value(self._current_line_index, "translation")

    @Property(str, notify=playbackLineChanged)
    def currentLineTime(self) -> str:
        return self._line_value(self._current_line_index, "time")

    @Property(int, notify=playbackLineChanged)
    def currentLineSourceStart(self) -> int:
        return self._line_int_value(self._current_line_index, "sourceStart")

    @Property(int, notify=playbackLineChanged)
    def currentLineSourceEnd(self) -> int:
        return self._line_int_value(self._current_line_index, "sourceEnd")

    @Property(str, notify=playbackLineChanged)
    def nextLineText(self) -> str:
        return self._line_value(self._next_line_index(), "text")

    @Property(str, notify=playbackLineChanged)
    def nextLineTranslation(self) -> str:
        return self._line_value(self._next_line_index(), "translation")

    @Property(bool, notify=availabilityChanged)
    def availableForPlayback(self) -> bool:
        return self._available_for_playback

    @Property(bool, notify=followEnabledChanged)
    def followEnabled(self) -> bool:
        return self._follow_enabled

    @Slot(bool)
    def setFollowEnabled(self, enabled: bool) -> None:
        normalized = bool(enabled)
        if normalized == self._follow_enabled:
            return
        self._follow_enabled = normalized
        self.followEnabledChanged.emit()

    @Slot(int)
    def setPlaybackPosition(self, position: int) -> None:
        normalized = max(0, int(position))
        current_index = self._line_index_at(normalized)
        if (
            normalized == self._position
            and current_index == self._current_line_index
        ):
            return
        line_changed = current_index != self._current_line_index
        self._position = normalized
        self._current_line_index = current_index
        if line_changed:
            self.playbackLineChanged.emit()

    def _on_lyrics_state_changed(self) -> None:
        self._reload_lyrics(force=False)

    def _on_player_state_changed(self) -> None:
        normalized = max(
            0,
            int(getattr(self._audio_player, "position", 0)),
        )
        current_index = self._line_index_at(normalized)
        available = self._compute_available_for_playback()
        line_changed = current_index != self._current_line_index
        availability_changed = available != self._available_for_playback
        self._position = normalized
        self._current_line_index = current_index
        self._available_for_playback = available
        if line_changed:
            self.playbackLineChanged.emit()
        if availability_changed:
            self.availabilityChanged.emit()

    def _reload_lyrics(self, *, force: bool) -> None:
        text = str(getattr(self._edit_session, "draftLyrics", "") or "")
        if not force and text == self._lyrics_text:
            return
        self._lyrics_text = text
        self._lines, self._timeline = self._parse_lines(text)
        self._timeline_positions = [timestamp for timestamp, _ in self._timeline]
        previous_availability = self._available_for_playback
        self._current_line_index = self._line_index_at(self._position)
        self._available_for_playback = self._compute_available_for_playback()
        self.linesChanged.emit()
        self.playbackLineChanged.emit()
        if self._available_for_playback != previous_availability or force:
            self.availabilityChanged.emit()

    def _compute_available_for_playback(self) -> bool:
        return bool(
            self._timeline
            and getattr(self._audio_player, "hasPlaybackSource", False)
            and getattr(self._audio_player, "playbackMatchesEditorFile", False)
        )

    def _line_index_at(self, position: int) -> int:
        if not self._timeline_positions:
            return -1
        timeline_index = bisect_right(self._timeline_positions, position) - 1
        if timeline_index < 0:
            return -1
        return self._timeline[timeline_index][1]

    def _next_line_index(self) -> int:
        for timestamp, line_index in self._timeline:
            if timestamp <= self._position:
                continue
            if line_index != self._current_line_index:
                return line_index
        return -1

    def _line_value(self, index: int, key: str) -> str:
        if index < 0 or index >= len(self._lines):
            return ""
        return str(self._lines[index].get(key) or "")

    def _line_int_value(self, index: int, key: str) -> int:
        if index < 0 or index >= len(self._lines):
            return -1
        return int(self._lines[index].get(key, -1))

    @classmethod
    def _parse_lines(
        cls,
        text: str,
    ) -> tuple[list[dict[str, object]], list[tuple[int, int]]]:
        lines: list[dict[str, object]] = []
        timeline: list[tuple[int, int]] = []
        source_position = 0
        for source_line in str(text or "").splitlines(keepends=True):
            raw_line = source_line.rstrip("\r\n")
            source_start = source_position
            source_end = source_start + cls._qml_text_length(raw_line)
            source_position += cls._qml_text_length(source_line)
            timed_match = cls._TIMED_LINE_RE.match(raw_line)
            if not timed_match:
                lines.append(
                    {
                        "index": len(lines) + 1,
                        "time": "",
                        "timeMs": -1,
                        "text": raw_line.strip(),
                        "translation": "",
                        "raw": raw_line,
                        "hasTimestamp": False,
                        "sourceStart": source_start,
                        "sourceEnd": source_end,
                    }
                )
                continue

            timestamp_matches = list(
                cls._TIMESTAMP_RE.finditer(timed_match.group(1))
            )
            if not timestamp_matches:
                continue
            timestamps = [cls._timestamp_ms(match) for match in timestamp_matches]
            lyric_text = timed_match.group(2).strip()
            first_timestamp = timestamps[0]

            if (
                lines
                and bool(lines[-1].get("hasTimestamp"))
                and int(lines[-1].get("timeMs", -1)) == first_timestamp
            ):
                line_index = len(lines) - 1
                existing_translation = str(
                    lines[line_index].get("translation") or ""
                )
                lines[line_index]["translation"] = (
                    f"{existing_translation} / {lyric_text}"
                    if existing_translation and lyric_text
                    else lyric_text or existing_translation
                )
                lines[line_index]["sourceEnd"] = source_end
            else:
                line_index = len(lines)
                lines.append(
                    {
                        "index": line_index + 1,
                        "time": timestamp_matches[0].group(0).strip("[]"),
                        "timeMs": first_timestamp,
                        "text": lyric_text,
                        "translation": "",
                        "raw": raw_line,
                        "hasTimestamp": True,
                        "sourceStart": source_start,
                        "sourceEnd": source_end,
                    }
                )

            timeline.extend((timestamp, line_index) for timestamp in timestamps)

        timeline.sort(key=lambda item: item[0])
        return lines, timeline

    @staticmethod
    def _qml_text_length(text: str) -> int:
        """Return the UTF-16 code-unit length used by QML TextEdit positions."""
        return len(str(text).encode("utf-16-le")) // 2

    @staticmethod
    def _timestamp_ms(match: re.Match[str]) -> int:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        fraction = str(match.group(3) or "")
        milliseconds = int(fraction.ljust(3, "0")[:3]) if fraction else 0
        return (minutes * 60 + seconds) * 1000 + milliseconds

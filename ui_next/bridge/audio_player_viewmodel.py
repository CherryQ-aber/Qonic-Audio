from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

from ui_next.bridge.base_viewmodel import BaseViewModel
from ui_next.bridge.capabilities import AUDIO_PLAYBACK, CapabilityGate


class _NullAudioOutput(QObject):
    """Preview/test backend that never initializes a system audio device."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._volume = 0.7
        self._device = None

    def setVolume(self, value: float) -> None:
        self._volume = float(value)

    def setDevice(self, device) -> None:
        self._device = device

    def device(self):
        return self._device


class _NullMediaPlayer(QObject):
    """Signal-compatible no-op player used while real playback is forbidden."""

    playbackStateChanged = Signal(object)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    mediaStatusChanged = Signal(object)
    errorOccurred = Signal(object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source = QUrl()
        self._position = 0
        self._audio_output = None

    def setAudioOutput(self, output) -> None:
        self._audio_output = output

    def setSource(self, source: QUrl) -> None:
        self._source = source

    def source(self) -> QUrl:
        return self._source

    def play(self) -> None:
        return

    def pause(self) -> None:
        return

    def stop(self) -> None:
        return

    def setPosition(self, position: int) -> None:
        self._position = int(position)

    def duration(self) -> int:
        return 0

    def errorString(self) -> str:
        return ""


class AudioPlayerViewModel(BaseViewModel):
    """Single capability-gated Qt Multimedia owner for the QML process."""

    stateChanged = Signal()

    _SOURCE_TYPE_LABELS = {
        "none": "未加载",
        "original": "原音频",
        "preview_cache": "试听版本",
        "export_result": "导出结果",
    }

    def __init__(
        self,
        file_session,
        capability_gate: CapabilityGate | None = None,
        *,
        media_player=None,
        audio_output=None,
    ) -> None:
        super().__init__(capability_gate=capability_gate)
        self._file_session = file_session
        self._backend_initialized = bool(
            self.allows_capability(AUDIO_PLAYBACK)
            and not self.capabilityGate.previewMode
        )
        self._player = (
            media_player
            if media_player is not None
            else QMediaPlayer(self)
            if self._backend_initialized
            else _NullMediaPlayer(self)
        )
        self._audio_output = (
            audio_output
            if audio_output is not None
            else QAudioOutput(self)
            if self._backend_initialized
            else _NullAudioOutput(self)
        )
        self._player.setAudioOutput(self._audio_output)

        self._state = "empty"
        self._duration = 0
        self._position = 0
        self._volume = 70
        self._error = ""
        self._playback_source_path = ""
        self._playback_source_label = "未加载"
        self._playback_source_type = "none"
        self._source_generation = 0
        self._playback_token = 0
        self._media_loaded = False
        self._ignore_backend_events = False
        self._signal_bindings: list[tuple[object, object]] = []
        self._release_snapshot: dict[str, object] | None = None
        self._devices_by_id: dict[str, object] = {}
        self._output_devices: list[dict[str, object]] = []
        self._selected_device_id = ""
        self._device_name = "系统默认输出" if self._backend_initialized else ""
        self._audio_output.setVolume(self._volume / 100.0)
        self._rebind_player_signals()

        self._file_session.currentFileChanged.connect(self.loadFile)
        self._file_session.currentFileCleared.connect(self.clear)
        if hasattr(self._file_session, "currentFileMissing"):
            self._file_session.currentFileMissing.connect(
                self._on_current_file_missing
            )
        self.set_status_message(
            "等待工作区音频。"
            if self._backend_initialized
            else "预览模式不会初始化音频输出或播放真实音频。"
        )

    @Property(bool, constant=True)
    def audioPlaybackEnabled(self) -> bool:
        return self.allows_capability(AUDIO_PLAYBACK)

    @Property(bool, constant=True)
    def backendInitialized(self) -> bool:
        return self._backend_initialized

    @Property(str, notify=stateChanged)
    def currentFilePath(self) -> str:
        return self._file_session.currentFilePath if self._file_session else ""

    @Property(str, notify=stateChanged)
    def currentFileName(self) -> str:
        return self._file_session.currentFileName if self._file_session else "未选择"

    @Property(str, notify=stateChanged)
    def currentPlaybackSourcePath(self) -> str:
        return self._playback_source_path

    @Property(str, notify=stateChanged)
    def currentPlaybackSourceLabel(self) -> str:
        return self._playback_source_label

    @Property(str, notify=stateChanged)
    def currentPlaybackSourceType(self) -> str:
        return self._playback_source_type

    @Property(str, notify=stateChanged)
    def currentPlaybackSourceTypeLabel(self) -> str:
        return self._SOURCE_TYPE_LABELS.get(
            self._playback_source_type,
            "音频来源",
        )

    @Property(bool, notify=stateChanged)
    def hasCurrentFile(self) -> bool:
        return bool(self.currentFilePath)

    @Property(str, notify=stateChanged)
    def playerState(self) -> str:
        return self._state

    @Property(int, notify=stateChanged)
    def duration(self) -> int:
        return self._duration

    @Property(int, notify=stateChanged)
    def position(self) -> int:
        return self._position

    @Property(int, notify=stateChanged)
    def volume(self) -> int:
        return self._volume

    @Property(str, notify=stateChanged)
    def error(self) -> str:
        return self._error

    @Property(str, notify=stateChanged)
    def outputDeviceName(self) -> str:
        return self._device_name

    @Property(str, notify=stateChanged)
    def outputDeviceStatus(self) -> str:
        if not self._backend_initialized:
            return "预览模式未初始化"
        if not self._output_devices:
            return "使用当前输出；展开列表时刷新"
        return "已连接" if self._device_name else "未检测到输出设备"

    @Property("QVariantList", notify=stateChanged)
    def outputDevices(self) -> list[dict[str, object]]:
        return [dict(item) for item in self._output_devices]

    @Property(str, notify=stateChanged)
    def selectedOutputDeviceId(self) -> str:
        return self._selected_device_id

    @Property(bool, notify=stateChanged)
    def mediaSourceReleased(self) -> bool:
        return self._state == "released" and not self._playback_source_path

    @Property(bool, notify=stateChanged)
    def canPlay(self) -> bool:
        return (
            self._backend_initialized
            and bool(self._playback_source_path)
            and self._state in {"ready", "paused", "stopped", "finished"}
        )

    @Slot(str, int)
    def loadFile(self, path: str, generation: int = 0) -> None:
        if generation and generation < self._source_generation:
            return
        self._source_generation = int(generation)
        if not path:
            self.clear()
            return
        if not self._backend_initialized:
            self._state = "empty"
            self._emit_state("预览模式不会加载或输出真实音频。")
            return
        self._set_playback_source(path, "原音频", "original", False, 0)

    @Slot(str, str, bool, int)
    def setPlaybackSource(
        self,
        path: str,
        label: str = "原音频",
        autoplay: bool = False,
        position: int = 0,
    ) -> None:
        """Compatibility entry: switch only the player, never FileSession."""
        source_type = self._infer_source_type(path, label)
        self._set_playback_source(path, label, source_type, autoplay, position)

    @Slot(str, str, str, bool, int)
    def setPlaybackSourceWithType(
        self,
        path: str,
        label: str,
        source_type: str,
        autoplay: bool = False,
        position: int = 0,
    ) -> None:
        self._set_playback_source(
            path,
            label,
            source_type,
            autoplay,
            position,
        )

    def _set_playback_source(
        self,
        path: str,
        label: str,
        source_type: str,
        autoplay: bool,
        position: int,
    ) -> None:
        if not path:
            self.clear()
            return
        if not self._backend_initialized:
            self._state = "empty"
            self._emit_state("预览模式不会加载或输出真实音频。")
            return
        source_path = str(Path(path).expanduser().resolve())
        if not Path(source_path).is_file():
            self._handle_missing_source(source_path)
            return

        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._release_snapshot = None
        self._state = "loading"
        self._error = ""
        self._media_loaded = False
        self._playback_source_path = source_path
        self._playback_source_label = str(label or "音频")
        self._playback_source_type = (
            source_type if source_type in self._SOURCE_TYPE_LABELS else "original"
        )
        self._player.setSource(QUrl.fromLocalFile(source_path))
        if position > 0:
            self._player.setPosition(max(0, int(position)))
        if autoplay:
            self._player.play()
        self._emit_state(f"正在加载{self._playback_source_label}。")

    @Slot()
    def returnToOriginal(self) -> None:
        if not self.currentFilePath:
            self._emit_state("请先导入音频。")
            return
        self._set_playback_source(
            self.currentFilePath,
            "原音频",
            "original",
            False,
            0,
        )

    @Slot()
    def play(self) -> None:
        if not self._backend_initialized:
            self._state = "error"
            self._error = "预览模式不会播放真实音频。"
            self._emit_state(self._error)
            return
        if not self._playback_source_path:
            self._state = "empty"
            self._emit_state("请先选择当前工作区音频文件。")
            return
        if not Path(self._playback_source_path).is_file():
            self._handle_missing_source(self._playback_source_path)
            return
        if self._state == "finished":
            self._player.setPosition(0)
        self._player.play()

    @Slot()
    def pause(self) -> None:
        if self._state == "playing":
            self._player.pause()

    @Slot()
    def stop(self) -> None:
        if self._state in {
            "playing",
            "paused",
            "ready",
            "stopped",
            "finished",
        }:
            self._player.stop()
            self._player.setPosition(0)
            self._position = 0
            self._state = "stopped" if self._playback_source_path else "empty"
            self._emit_state("播放已停止并返回开头。")

    @Slot(float)
    def seek(self, position: float) -> None:
        if (
            self._duration <= 0
            or not self._backend_initialized
            or not self._playback_source_path
        ):
            return
        self._player.setPosition(
            max(0, min(int(round(position)), self._duration))
        )

    @Slot(float)
    def setVolume(self, value: float) -> None:
        self._volume = max(0, min(int(round(value)), 100))
        self._audio_output.setVolume(self._volume / 100.0)
        self._emit_state("音量已更新；不会在拖动时保存配置。")

    @Slot(result=bool)
    def releaseMediaSource(self) -> bool:
        """Release the Qt media handle while preserving the edit session."""
        self._release_snapshot = {
            "path": self._playback_source_path,
            "label": self._playback_source_label,
            "source_type": self._playback_source_type,
            "position": self._position,
            "was_playing": self._state == "playing",
        }
        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._playback_source_path = ""
        self._playback_source_label = "已释放"
        self._playback_source_type = "none"
        self._state = "released" if self.hasCurrentFile else "empty"
        self._error = ""
        released = self._backend_source_is_empty()
        self._emit_state(
            "播放器已释放媒体源，可继续执行文件操作。"
            if released
            else "播放器未能确认媒体源已释放。"
        )
        return released

    @Slot(result=bool)
    def prepareForFileOperation(self) -> bool:
        return self.releaseMediaSource()

    @Slot(result=bool)
    def restorePlaybackSource(self) -> bool:
        snapshot = dict(self._release_snapshot or {})
        path = str(snapshot.get("path") or self.currentFilePath or "")
        if not path or not Path(path).is_file():
            self._handle_missing_source(path)
            return False
        self._release_snapshot = None
        self._set_playback_source(
            path,
            str(snapshot.get("label") or "原音频"),
            str(snapshot.get("source_type") or "original"),
            False,
            int(snapshot.get("position") or 0),
        )
        return True

    @Slot()
    def refreshOutputDevices(self) -> None:
        """Refresh choices without switching a still-available device."""
        if not self._backend_initialized:
            self._output_devices = []
            self._devices_by_id = {}
            self._emit_state("预览模式不会枚举真实音频输出设备。")
            return
        try:
            devices = list(QMediaDevices.audioOutputs())
            default_device = QMediaDevices.defaultAudioOutput()
        except Exception as exc:
            self._output_devices = []
            self._devices_by_id = {}
            self._error = f"无法刷新音频输出设备：{exc}"
            self._emit_state(self._error)
            return

        current_device = self._current_audio_device()
        current_id = self._device_id(current_device)
        previous_id = self._selected_device_id or current_id
        default_id = self._device_id(default_device)
        items: list[dict[str, object]] = []
        devices_by_id: dict[str, object] = {}
        for index, device in enumerate(devices):
            device_id = self._device_id(device) or f"device-{index}"
            name = self._device_name_for(device) or f"音频输出 {index + 1}"
            devices_by_id[device_id] = device
            items.append(
                {
                    "id": device_id,
                    "name": name,
                    "isDefault": bool(default_id and device_id == default_id),
                }
            )

        self._devices_by_id = devices_by_id
        self._output_devices = items
        if previous_id and previous_id in devices_by_id:
            self._selected_device_id = previous_id
            self._device_name = self._device_name_for(devices_by_id[previous_id])
            message = "音频输出设备列表已刷新；当前设备保持不变。"
        elif previous_id and devices:
            fallback = devices_by_id.get(default_id, devices[0])
            try:
                self._audio_output.setDevice(fallback)
                self._audio_output.setVolume(self._volume / 100.0)
                self._selected_device_id = self._device_id(fallback)
                self._device_name = self._device_name_for(fallback)
                message = "原输出设备已不可用，已安全回退到系统默认设备。"
            except Exception as exc:
                self._error = f"输出设备已消失，回退失败：{exc}"
                message = self._error
        else:
            selected = devices_by_id.get(current_id) or devices_by_id.get(default_id)
            self._selected_device_id = self._device_id(selected)
            self._device_name = (
                self._device_name_for(selected)
                if selected is not None
                else ""
            )
            message = (
                "音频输出设备列表已刷新；未自动切换设备。"
                if devices
                else "当前未检测到音频输出设备。"
            )
        self._emit_state(message)

    @Slot(str, result=bool)
    def selectOutputDevice(self, device_id: str) -> bool:
        if not self._backend_initialized:
            self._emit_state("预览模式不会切换真实音频输出设备。")
            return False
        selected_id = str(device_id or "")
        device = self._devices_by_id.get(selected_id)
        if device is None:
            self._error = "所选音频输出设备已不可用。"
            self._emit_state(self._error)
            return False
        if selected_id == self._selected_device_id:
            self._emit_state("当前已使用所选音频输出设备。")
            return True
        previous_device = self._current_audio_device()
        previous_id = self._selected_device_id
        previous_name = self._device_name
        try:
            self._audio_output.setDevice(device)
            self._audio_output.setVolume(self._volume / 100.0)
        except Exception as exc:
            try:
                if previous_device is not None:
                    self._audio_output.setDevice(previous_device)
            except Exception:
                pass
            self._selected_device_id = previous_id
            self._device_name = previous_name
            self._error = f"切换音频输出设备失败：{exc}"
            self._emit_state(self._error)
            return False
        self._selected_device_id = selected_id
        self._device_name = self._device_name_for(device)
        self._error = ""
        self._emit_state(f"已切换音频输出设备：{self._device_name}")
        return True

    @Slot()
    def clear(self) -> None:
        self._release_snapshot = None
        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._state = "empty"
        self._error = ""
        self._playback_source_path = ""
        self._playback_source_label = "未加载"
        self._playback_source_type = "none"
        self._emit_state("当前文件已清除，播放器媒体源已释放。")

    @Slot()
    def shutdown(self) -> None:
        self._release_snapshot = None
        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._playback_source_path = ""
        self._playback_source_label = "未加载"
        self._playback_source_type = "none"
        self._state = "empty"

    def _clear_backend_source(self) -> None:
        self._ignore_backend_events = True
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        finally:
            self._ignore_backend_events = False
        self._position = 0
        self._duration = 0
        self._media_loaded = False

    def _rebind_player_signals(self) -> None:
        for signal, handler in self._signal_bindings:
            try:
                signal.disconnect(handler)
            except (RuntimeError, TypeError):
                pass
        self._signal_bindings = []
        token = self._playback_token
        bindings = (
            (
                self._player.playbackStateChanged,
                lambda state, current=token: self._on_playback_state_changed(
                    current, state
                ),
            ),
            (
                self._player.positionChanged,
                lambda position, current=token: self._on_position_changed(
                    current, position
                ),
            ),
            (
                self._player.durationChanged,
                lambda duration, current=token: self._on_duration_changed(
                    current, duration
                ),
            ),
            (
                self._player.mediaStatusChanged,
                lambda status, current=token: self._on_media_status_changed(
                    current, status
                ),
            ),
            (
                self._player.errorOccurred,
                lambda error, message, current=token: self._on_error(
                    current, error, message
                ),
            ),
        )
        for signal, handler in bindings:
            signal.connect(handler)
            self._signal_bindings.append((signal, handler))

    def _on_playback_state_changed(self, token: int, state) -> None:
        if not self._accept_event(token):
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._state = "playing"
            self._media_loaded = True
            message = f"正在播放{self._playback_source_label}。"
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._state = "paused"
            message = "播放已暂停。"
        elif self._state == "loading":
            return
        else:
            self._state = "stopped" if self._playback_source_path else "empty"
            message = "播放已停止。"
        self._emit_state(message)

    def _on_position_changed(self, token: int, position: int) -> None:
        if not self._accept_event(token) or not self._media_loaded:
            return
        self._position = max(0, int(position))
        self.stateChanged.emit()

    def _on_duration_changed(self, token: int, duration: int) -> None:
        if not self._accept_event(token):
            return
        self._duration = max(0, int(duration))
        self.stateChanged.emit()

    def _on_media_status_changed(self, token: int, status) -> None:
        if not self._accept_event(token):
            return
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._media_loaded = True
            self._state = "ready"
            self._error = ""
            duration_getter = getattr(self._player, "duration", None)
            if callable(duration_getter):
                self._duration = max(0, int(duration_getter() or 0))
            self._emit_state("音频已加载，可以播放。")
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._media_loaded = True
            self._state = "finished"
            self._position = self._duration
            self._emit_state("播放已结束。")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._enter_terminal_error(
                self._classify_error(self._player.errorString())
            )

    def _on_error(self, token: int, _error, message: str) -> None:
        if not self._accept_event(token):
            return
        self._enter_terminal_error(self._classify_error(message))

    def _accept_event(self, token: int) -> bool:
        return (
            not self._ignore_backend_events
            and token == self._playback_token
            and self._backend_source_matches_expected()
        )

    def _backend_source_matches_expected(self) -> bool:
        source = self._backend_source()
        if not self._playback_source_path:
            return source.isEmpty()
        if source.isEmpty():
            return self._state == "loading"
        try:
            return Path(source.toLocalFile()).resolve() == Path(
                self._playback_source_path
            ).resolve()
        except OSError:
            return source.toLocalFile() == self._playback_source_path

    def _backend_source(self) -> QUrl:
        source_member = getattr(self._player, "source", QUrl())
        source = source_member() if callable(source_member) else source_member
        return source if isinstance(source, QUrl) else QUrl()

    def _backend_source_is_empty(self) -> bool:
        return self._backend_source().isEmpty()

    def _handle_missing_source(self, path: str) -> None:
        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._state = "error"
        self._error = "当前音频文件已不存在，请重新选择文件。"
        self._playback_source_path = ""
        self._playback_source_label = "文件缺失"
        self._playback_source_type = "none"
        if (
            path
            and self.currentFilePath
            and self._same_path(path, self.currentFilePath)
            and hasattr(self._file_session, "markCurrentFileMissing")
        ):
            self._file_session.markCurrentFileMissing(self._error)
        self._emit_state(self._error)

    def _enter_terminal_error(self, message: str) -> None:
        """Release an unusable media handle while preserving FileSession."""
        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._state = "error"
        self._error = str(message or "音频加载或播放错误。")
        self._playback_source_path = ""
        self._playback_source_label = "加载失败"
        self._playback_source_type = "none"
        self._emit_state(self._error)

    @Slot(str, int)
    def _on_current_file_missing(self, path: str, _generation: int) -> None:
        if not path or not self.currentFilePath or not self._same_path(
            path, self.currentFilePath
        ):
            return
        self._playback_token += 1
        self._rebind_player_signals()
        self._clear_backend_source()
        self._state = "error"
        self._error = "当前音频文件已不存在，请重新选择文件。"
        self._playback_source_path = ""
        self._playback_source_label = "文件缺失"
        self._playback_source_type = "none"
        self._emit_state(self._error)

    def _classify_error(self, message: str) -> str:
        detail = str(message or "").strip()
        lower = detail.lower()
        if "permission" in lower or "access" in lower:
            return f"无法读取音频文件：{detail}"
        if "device" in lower or "audio output" in lower:
            return f"无法打开音频输出设备：{detail}"
        if "format" in lower or "codec" in lower or "unsupported" in lower:
            return f"当前播放器不支持该音频格式：{detail}"
        return f"音频加载或播放错误：{detail or '未知原因'}"

    def _infer_source_type(self, path: str, label: str) -> str:
        if path and self.currentFilePath and self._same_path(path, self.currentFilePath):
            return "original"
        lowered = str(label or "").casefold()
        if "试听" in lowered or "preview" in lowered:
            return "preview_cache"
        if "导出" in lowered or "export" in lowered:
            return "export_result"
        return "original"

    def _current_audio_device(self):
        getter = getattr(self._audio_output, "device", None)
        try:
            return getter() if callable(getter) else None
        except Exception:
            return None

    @staticmethod
    def _device_id(device) -> str:
        if device is None:
            return ""
        getter = getattr(device, "id", None)
        try:
            raw = getter() if callable(getter) else b""
            if hasattr(raw, "data"):
                raw = raw.data()
            if isinstance(raw, str):
                return raw
            return bytes(raw).hex()
        except Exception:
            return ""

    @staticmethod
    def _device_name_for(device) -> str:
        if device is None:
            return ""
        getter = getattr(device, "description", None)
        try:
            return str(getter() if callable(getter) else "")
        except Exception:
            return ""

    @staticmethod
    def _same_path(left: str, right: str) -> bool:
        try:
            return Path(left).resolve() == Path(right).resolve()
        except OSError:
            return str(left) == str(right)

    def _emit_state(self, message: str) -> None:
        self.set_status_message(message)
        self.stateChanged.emit()

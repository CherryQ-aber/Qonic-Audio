import array
import hashlib
import json
import os
import subprocess
import sys

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


DEFAULT_SAMPLE_POINTS = 2000
DEFAULT_SAMPLE_RATE = 8000


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


class WaveformCacheManager:

    def __init__(self, cache_dir):
        self.cache_dir = os.path.normpath(os.path.abspath(cache_dir))
        os.makedirs(self.cache_dir, exist_ok=True)

    def _source_info(self, source_path):
        stat = os.stat(source_path)
        return {
            "source_path": os.path.normcase(os.path.abspath(source_path)),
            "file_size": int(stat.st_size),
            "mtime": float(stat.st_mtime),
        }

    def cache_path_for(self, source_path):
        info = self._source_info(source_path)
        key_text = "|".join(
            (
                info["source_path"],
                str(info["file_size"]),
                f"{info['mtime']:.6f}",
            )
        )
        key = hashlib.sha256(key_text.encode("utf-8", errors="ignore")).hexdigest()
        return os.path.join(self.cache_dir, f"{key}.json")

    def load(self, source_path, sample_points):
        cache_path = self.cache_path_for(source_path)

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            info = self._source_info(source_path)
            if (
                payload.get("source_path") == info["source_path"]
                and int(payload.get("file_size", -1)) == info["file_size"]
                and abs(float(payload.get("mtime", -1)) - info["mtime"]) < 0.001
                and int(payload.get("sample_points", 0)) == int(sample_points)
            ):
                peaks = payload.get("peaks") or []
                if isinstance(peaks, list) and peaks:
                    return payload
        except Exception:
            return None

        return None

    def save(self, source_path, duration_ms, sample_points, peaks):
        cache_path = self.cache_path_for(source_path)
        info = self._source_info(source_path)
        payload = {
            **info,
            "duration_ms": int(duration_ms or 0),
            "sample_points": int(sample_points),
            "peaks": [round(float(value), 5) for value in peaks],
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

        return payload


def _compress_peaks(raw_peaks, sample_points):
    if not raw_peaks:
        return []

    if len(raw_peaks) <= sample_points:
        return raw_peaks

    compressed = []
    total = len(raw_peaks)
    for index in range(sample_points):
        start = int(index * total / sample_points)
        end = int((index + 1) * total / sample_points)
        bucket = raw_peaks[start:max(end, start + 1)]
        compressed.append(max(bucket) if bucket else 0.0)

    return compressed


def generate_waveform_peaks(
    audio_path,
    ffmpeg_path,
    sample_points=DEFAULT_SAMPLE_POINTS,
    sample_rate=DEFAULT_SAMPLE_RATE,
    stop_check=None,
):
    if not os.path.isfile(audio_path):
        return {"success": False, "error": "音频文件不存在。"}

    if not os.path.isfile(ffmpeg_path):
        return {"success": False, "error": "FFmpeg 不存在，无法生成波形。"}

    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        audio_path,
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        **_get_hidden_subprocess_kwargs(),
    )
    raw_peaks = []
    window_samples = max(1, sample_rate // 50)
    window_peak = 0
    window_count = 0
    total_samples = 0
    leftover = b""

    try:
        while True:
            if stop_check and stop_check():
                process.terminate()
                return {"success": False, "stopped": True, "error": "波形生成已取消。"}

            chunk = process.stdout.read(32768)
            if not chunk:
                break

            data = leftover + chunk
            if len(data) % 2:
                leftover = data[-1:]
                data = data[:-1]
            else:
                leftover = b""

            if not data:
                continue

            samples = array.array("h")
            samples.frombytes(data)
            if sys.byteorder != "little":
                samples.byteswap()

            for sample in samples:
                value = abs(int(sample))
                if value > window_peak:
                    window_peak = value
                window_count += 1
                total_samples += 1

                if window_count >= window_samples:
                    raw_peaks.append(min(1.0, window_peak / 32768.0))
                    window_peak = 0
                    window_count = 0

        if window_count:
            raw_peaks.append(min(1.0, window_peak / 32768.0))

        stderr = process.stderr.read().decode("utf-8", errors="ignore").strip()
        return_code = process.wait()
        if return_code != 0:
            return {
                "success": False,
                "error": stderr or f"FFmpeg 退出码: {return_code}",
            }

        peaks = _compress_peaks(raw_peaks, sample_points)
        if not peaks:
            return {"success": False, "error": "未读取到可用音频采样。"}

        duration_ms = int(total_samples * 1000 / sample_rate) if sample_rate else 0
        return {
            "success": True,
            "duration_ms": duration_ms,
            "sample_points": int(sample_points),
            "peaks": peaks,
        }

    finally:
        try:
            if process.poll() is None:
                process.terminate()
        except Exception:
            pass


class WaveformGenerateThread(QThread):
    finished_signal = Signal(dict)

    def __init__(self, audio_path, cache_dir, ffmpeg_path, sample_points=DEFAULT_SAMPLE_POINTS, parent=None):
        super().__init__(parent)
        self.audio_path = os.path.normpath(os.path.abspath(audio_path))
        self.cache_dir = cache_dir
        self.ffmpeg_path = ffmpeg_path
        self.sample_points = int(sample_points)
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def _should_stop(self):
        return self._stop_requested

    def run(self):
        try:
            cache = WaveformCacheManager(self.cache_dir)
            cached = cache.load(self.audio_path, self.sample_points)
            if cached:
                self.finished_signal.emit(
                    {
                        "success": True,
                        "source_path": self.audio_path,
                        "from_cache": True,
                        "duration_ms": cached.get("duration_ms", 0),
                        "sample_points": cached.get("sample_points", self.sample_points),
                        "peaks": cached.get("peaks") or [],
                    }
                )
                return

            result = generate_waveform_peaks(
                self.audio_path,
                self.ffmpeg_path,
                sample_points=self.sample_points,
                stop_check=self._should_stop,
            )

            if self._stop_requested:
                result = {"success": False, "stopped": True, "error": "波形生成已取消。"}

            if result.get("success"):
                payload = cache.save(
                    self.audio_path,
                    result.get("duration_ms", 0),
                    self.sample_points,
                    result.get("peaks") or [],
                )
                result.update(payload)

            result["source_path"] = self.audio_path
            result["from_cache"] = False
            self.finished_signal.emit(result)

        except Exception as e:
            self.finished_signal.emit(
                {
                    "success": False,
                    "source_path": self.audio_path,
                    "error": str(e),
                }
            )


class WaveformWidget(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks = []
        self.position_ratio = 0.0
        self.status_text = "波形预览：未加载"
        self.setMinimumHeight(88)
        self.setMaximumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def set_peaks(self, peaks):
        self.peaks = [max(0.0, min(1.0, float(value))) for value in (peaks or [])]
        self.update()

    def clear_waveform(self):
        self.peaks = []
        self.position_ratio = 0.0
        self.status_text = "波形预览：未加载"
        self.update()

    def set_position_ratio(self, ratio):
        self.position_ratio = max(0.0, min(1.0, float(ratio or 0.0)))
        self.update()

    def set_status_text(self, text):
        self.status_text = text or ""
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.peaks and self.width() > 0:
            if hasattr(event, "position"):
                x = event.position().x()
            else:
                x = event.pos().x()
            ratio = max(0.0, min(1.0, float(x) / max(1.0, float(self.width() - 1))))
            self.seek_requested.emit(ratio)
            event.accept()
            return

        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        rect = self.rect().adjusted(1, 1, -1, -1)
        palette = self.palette()
        background = palette.window().color()
        border = palette.mid().color()
        wave_color = QColor(88, 166, 255)
        center_color = palette.midlight().color()
        cursor_color = QColor(255, 190, 92)

        painter.fillRect(rect, background)
        painter.setPen(QPen(border, 1))
        painter.drawRect(rect)

        if not self.peaks:
            painter.setPen(palette.text().color())
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.status_text)
            return

        center_y = rect.center().y()
        painter.setPen(QPen(center_color, 1))
        painter.drawLine(rect.left() + 4, center_y, rect.right() - 4, center_y)

        usable_width = max(1, rect.width() - 8)
        usable_height = max(2, rect.height() - 18)
        left = rect.left() + 4
        top = rect.top() + 9
        peak_count = len(self.peaks)
        painter.setPen(QPen(wave_color, 1))

        for x in range(usable_width):
            start = int(x * peak_count / usable_width)
            end = int((x + 1) * peak_count / usable_width)
            bucket = self.peaks[start:max(end, start + 1)]
            peak = max(bucket) if bucket else 0.0
            half_height = max(1, int((usable_height / 2) * peak))
            painter.drawLine(
                left + x,
                center_y - half_height,
                left + x,
                center_y + half_height,
            )

        cursor_x = left + int(self.position_ratio * usable_width)
        painter.setPen(QPen(cursor_color, 2))
        painter.drawLine(cursor_x, top, cursor_x, top + usable_height)

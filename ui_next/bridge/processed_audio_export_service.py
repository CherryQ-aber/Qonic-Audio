"""No-clobber publication of a processed audio temp file."""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from ui_next.bridge.audio_processing_service import AudioProcessingService
from ui_next.bridge.no_clobber_publish import publish_no_clobber


class ProcessedAudioExportService:
    def __init__(self, processing_service: AudioProcessingService | None = None) -> None:
        self.processing_service = processing_service or AudioProcessingService()

    def cancel(self) -> None:
        self.processing_service.cancel()

    def export(self, source_path: str, output_path: str, semitone: int) -> dict:
        validation = self._validate(source_path, output_path, semitone)
        if not validation["success"]:
            return validation
        source, output = Path(validation["source"]), Path(validation["output"])
        source_sha = self._sha256(source)
        temp = output.parent / f".{output.stem}.pitch-{uuid.uuid4().hex}{output.suffix}"
        render = self.processing_service.render_pitch_shift(str(source), str(temp), int(semitone))
        if not render.get("success"):
            return render
        if self.processing_service.cancel_requested:
            self.processing_service.cleanup_owned(temp)
            return self._failure("processing_cancelled", "处理已取消；未发布正式输出。")
        if self._sha256(source) != source_sha:
            self.processing_service.cleanup_owned(temp)
            return self._failure("source_modified", "源文件在处理期间发生变化，已取消发布。")
        preservation = self._verify_preservation(source, temp)
        if not preservation["success"]:
            self.processing_service.cleanup_owned(temp)
            return preservation
        if self.processing_service.cancel_requested:
            self.processing_service.cleanup_owned(temp)
            return self._failure("processing_cancelled", "处理已取消；未发布正式输出。")
        published = publish_no_clobber(temp, output)
        if not published.get("success"):
            return self._failure(str(published.get("error_code") or "output_conflict"), str(published.get("message") or "发布失败。"), publish=published)
        warnings = list(preservation.get("warnings") or [])
        return {
            "success": True,
            "source_sha256": source_sha,
            "preservation": preservation,
            "publish": published,
            **render,
            "output_path": str(output),
            "appliedModules": ["pitch"],
            "skippedModules": [],
            "failedModules": [],
            "warnings": warnings,
            "sourceUnchanged": True,
        }

    @staticmethod
    def _validate(source_path: str, output_path: str, semitone: int) -> dict:
        raw_source, raw_output = str(source_path or "").strip(), str(output_path or "").strip()
        if not raw_output:
            return ProcessedAudioExportService._failure("output_required", "必须手动选择新的输出路径。")
        try:
            source, output = Path(raw_source).resolve(), Path(raw_output).resolve()
        except OSError as exc:
            return ProcessedAudioExportService._failure("output_required", f"无法规范化输出路径：{exc}")
        if not source.is_file():
            return ProcessedAudioExportService._failure("source_missing", "当前源音频不存在。")
        if source == output:
            return ProcessedAudioExportService._failure("output_same_as_source", "输出路径不能与当前源文件相同。")
        if source.suffix.lower() != output.suffix.lower():
            return ProcessedAudioExportService._failure("output_extension_mismatch", "本阶段输出格式必须跟随源文件。")
        if output.exists():
            return ProcessedAudioExportService._failure("output_exists", "输出路径已存在，系统不会覆盖。")
        if int(semitone) == 0:
            return ProcessedAudioExportService._failure("pitch_zero_no_processing", "0 半音无需导出 Pitch Shift 文件。")
        return {"success": True, "source": str(source), "output": str(output)}

    @staticmethod
    def _verify_preservation(source: Path, output: Path) -> dict:
        # FFmpeg maps source streams/metadata in the render command.  Readback
        # is deliberately conservative: only fail when a readable source value
        # demonstrably disappears from the processed temporary file.
        try:
            from metadata import read_audio_metadata, read_cover_preview
            from lyrics import read_embedded_lyrics
            source_meta, output_meta = read_audio_metadata(str(source), include_cover=False), read_audio_metadata(str(output), include_cover=False)
            for key in ("title", "artist", "album", "year", "genre", "track"):
                if source_meta.get(key) and source_meta.get(key) != output_meta.get(key):
                    return ProcessedAudioExportService._failure("metadata_preservation_failed", "处理结果未保留源文件元数据。")
            source_cover, output_cover = read_cover_preview(str(source)), read_cover_preview(str(output))
            if source_cover.get("has_cover") and not output_cover.get("has_cover"):
                return ProcessedAudioExportService._failure("cover_preservation_failed", "处理结果未保留源文件封面。")
            source_lyrics, output_lyrics = read_embedded_lyrics(str(source)), read_embedded_lyrics(str(output))
            source_lyrics_text = str(source_lyrics.get("lyrics_text") or "")
            output_lyrics_text = str(output_lyrics.get("lyrics_text") or "")
            if source_lyrics_text and source_lyrics_text != output_lyrics_text:
                return ProcessedAudioExportService._failure("lyrics_preservation_failed", "处理结果未保留源文件内嵌歌词。")
        except Exception as exc:
            return ProcessedAudioExportService._failure("metadata_preservation_failed", f"无法验证源文件信息保留：{exc}")
        return {"success": True, "warnings": []}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _failure(error_code: str, message: str, **extra) -> dict:
        return {
            "success": False,
            "error_code": error_code,
            "message": message,
            "appliedModules": [],
            "skippedModules": [],
            "failedModules": ["pitch"],
            "warnings": [],
            "sourceUnchanged": True,
            **extra,
        }

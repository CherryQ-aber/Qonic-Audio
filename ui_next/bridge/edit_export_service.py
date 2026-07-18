from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import os
from pathlib import Path
import shutil
from threading import Event
from uuid import uuid4

from metadata import (
    read_audio_metadata,
    read_cover_preview,
    remove_audio_cover,
    write_audio_cover,
    write_audio_metadata,
)
from lyrics import (
    embed_lrc_to_audio,
    read_embedded_lyrics,
    read_lrc_file_preview,
    remove_embedded_lyrics,
)
from ui_next.bridge.capabilities import COVER_WRITE, LYRICS_WRITE, METADATA_WRITE, CapabilityGate
from ui_next.bridge.cover_validation import validate_cover_bytes
from ui_next.bridge.no_clobber_publish import cleanup_owned_temp, publish_no_clobber


_METADATA_WRITE_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus"}
)
_COVER_WRITE_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus"}
)
_LYRICS_WRITE_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus"}
)
_METADATA_FIELDS = (
    "title", "artist", "album", "albumartist", "date", "genre",
    "tracknumber", "discnumber", "bpm", "initialkey", "comment",
)
_METADATA_ALIASES = {
    "albumartist": ("albumartist", "album_artist"),
    "date": ("date", "year"),
    "tracknumber": ("tracknumber", "track"),
    "discnumber": ("discnumber", "disc"),
}
_METADATA_INPUT_ALIASES = {
    "album_artist": "albumartist",
    "year": "date",
    "track": "tracknumber",
    "disc": "discnumber",
}


@dataclass(frozen=True)
class EditExportRequest:
    source_path: str
    output_path: str
    metadata_changes: dict[str, str] | None = None
    lyrics_text: str | None = None
    cover_action: str = "keep"  # keep, replace, remove
    cover_data: bytes | None = None
    cover_mime: str = ""
    cancel_event: Event | None = field(default=None, repr=False, compare=False)

    def requested_operations(self) -> tuple[str, ...]:
        operations: list[str] = []
        if self.metadata_changes:
            operations.append("metadata")
        if self.cover_action in {"replace", "remove"}:
            operations.append("cover")
        if self.lyrics_text is not None:
            operations.append("lyrics")
        return tuple(operations)


@dataclass(frozen=True)
class LrcExportRequest:
    source_path: str
    output_path: str
    lyrics_text: str
    original_lrc_path: str = ""
    cancel_event: Event | None = field(default=None, repr=False, compare=False)


class EditExportService:
    """Create and publish a fully verified edited *copy* of an audio file."""

    def __init__(self, capability_gate: CapabilityGate | None = None) -> None:
        self._capability_gate = capability_gate or CapabilityGate()

    def export(self, request: EditExportRequest) -> dict[str, object]:
        result = _base_result(request)
        source, output, error = self._validate_paths(request)
        if error:
            return _fail(result, *error)

        operations = request.requested_operations()
        result["applied_operations"] = list(operations)
        result["appliedModules"] = list(operations)
        if not operations:
            return _fail(result, "no_changes", "没有待导出的编辑修改。")

        operation_error = self._validate_operations(source, request, operations)
        if operation_error:
            return _fail(result, *operation_error)

        required = _required_capabilities(operations)
        result["required_capabilities"] = list(required)
        denied = [capability for capability in required if not self._capability_gate.allows(capability)]
        if denied:
            return _fail(
                result,
                "capability_denied",
                "所选内容当前无法导出。未创建临时副本。",
            )
        if _cancelled(request):
            return _cancelled_result(result)

        # The legacy writer normalizes omitted editable fields to an empty
        # value. Complete the request from the source read only after the
        # capability gate has accepted it, so a denied export does not touch
        # either a temporary file or the metadata backend.
        if "metadata" in operations:
            merged_metadata, merge_error = _merged_metadata_changes(
                source, request.metadata_changes or {}
            )
            if merge_error:
                return _fail(result, *merge_error)
            request = replace(request, metadata_changes=merged_metadata)

        try:
            source_sha256 = _sha256(source)
        except OSError as exc:
            return _fail(result, "source_missing", f"无法校验源文件：{exc}")
        result["source_sha256"] = source_sha256
        if _cancelled(request):
            return _cancelled_result(result)

        try:
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _fail(result, "temp_copy_failed", f"无法创建输出目录：{exc}")

        temp_path = _make_temp_path(output)
        temp_identity: tuple[int, int] | None = None
        try:
            shutil.copy2(source, temp_path)
            temp_identity = _identity(temp_path)
        except OSError as exc:
            return _fail(result, "temp_copy_failed", f"无法创建编辑临时副本：{exc}")

        try:
            if _cancelled(request):
                return _cancelled_with_cleanup(result, temp_path, temp_identity)
            apply_error = self._apply_operations(temp_path, request, operations)
            if apply_error:
                return _fail_with_cleanup(result, temp_path, temp_identity, *apply_error)

            if _cancelled(request):
                return _cancelled_with_cleanup(result, temp_path, temp_identity)
            verification = self._verify(temp_path, request, operations)
            if verification:
                return _fail_with_cleanup(result, temp_path, temp_identity, *verification)

            if _sha256(source) != source_sha256:
                return _fail_with_cleanup(
                    result,
                    temp_path,
                    temp_identity,
                    "verification_failed",
                    "源文件在导出期间发生变化，已拒绝发布编辑副本。",
                )

            if _cancelled(request):
                return _cancelled_with_cleanup(result, temp_path, temp_identity)
            published = publish_no_clobber(temp_path, output)
            result["finalization_strategy"] = published["finalization_strategy"]
            result["temp_cleanup_success"] = published["temp_cleanup_success"]
            if not published["success"]:
                return _fail(result, str(published["error_code"]), str(published["message"]))

            post_verification = self._verify(output, request, operations)
            if post_verification:
                final_cleanup_ok = cleanup_owned_temp(
                    output,
                    published.get("output_identity"),
                )
                if not final_cleanup_ok:
                    result["warnings"].append("发布后验证失败，无法确认清理输出文件。")
                return _fail(result, "verification_failed", post_verification[1])

            result.update(
                {
                    "success": True,
                    "message": "已安全导出编辑副本；原文件未修改。",
                    "verification_success": True,
                    "source_sha256": source_sha256,
                    "sourceUnchanged": True,
                }
            )
            return result
        except Exception as exc:  # defensive transaction boundary
            return _fail_with_cleanup(
                result,
                temp_path,
                temp_identity,
                "finalization_failed",
                f"编辑副本导出异常：{exc}",
            )

    def export_lrc(self, request: LrcExportRequest) -> dict[str, object]:
        """Publish a UTF-8 (without BOM) LRC file without overwriting a path."""
        result = _base_lrc_result(request)
        raw_output = str(request.output_path or "").strip()
        text = str(request.lyrics_text or "")
        if not raw_output:
            return _fail(result, "lrc_output_required", "必须手动选择全新的 .lrc 输出路径。")
        if not text.strip():
            return _fail(result, "lyrics_draft_empty", "空歌词不会被解释为删除操作；请恢复原始歌词或输入内容。")
        if not self._capability_gate.allows(LYRICS_WRITE):
            return _fail(result, "capability_denied", "当前无法导出歌词。未创建临时文件。")
        if _cancelled(request):
            return _cancelled_result(result)
        try:
            output = Path(raw_output).expanduser().resolve()
        except OSError as exc:
            return _fail(result, "lrc_output_required", f"无法规范化 LRC 输出路径：{exc}")
        if output.suffix.lower() != ".lrc":
            return _fail(result, "lrc_extension_invalid", "LRC 输出文件必须使用 .lrc 扩展名。")
        original_lrc = str(request.original_lrc_path or "").strip()
        if original_lrc:
            try:
                if _same_path(Path(original_lrc).expanduser().resolve(), output):
                    return _fail(result, "lrc_output_exists", "不能覆盖原始 .lrc 文件；请选择新的输出路径。")
            except OSError:
                pass
        if output.exists():
            return _fail(result, "lrc_output_exists", "输出路径已存在，系统不会覆盖已有 .lrc 文件。")
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _fail(result, "lrc_temp_write_failed", f"无法创建 LRC 输出目录：{exc}")

        temp_path = output.parent / f".{output.stem}.cherryq_lyrics_{uuid4().hex}.tmp.lrc"
        temp_identity: tuple[int, int] | None = None
        try:
            temp_path.write_bytes(text.encode("utf-8"))
            temp_identity = _identity(temp_path)
            if _cancelled(request):
                return _cancelled_with_cleanup(result, temp_path, temp_identity)
            verification = read_lrc_file_preview(str(temp_path))
            if not verification.get("ok") or str(verification.get("lyrics_text") or "") != text:
                return _fail_with_cleanup(
                    result, temp_path, temp_identity,
                    "lyrics_verification_failed", "无法验证临时 LRC 内容。",
                )
            if _cancelled(request):
                return _cancelled_with_cleanup(result, temp_path, temp_identity)
            published = publish_no_clobber(temp_path, output)
            result["finalization_strategy"] = published["finalization_strategy"]
            result["temp_cleanup_success"] = published["temp_cleanup_success"]
            if not published["success"]:
                return _fail(result, str(published["error_code"]), str(published["message"]))
            verification = read_lrc_file_preview(str(output))
            if not verification.get("ok") or str(verification.get("lyrics_text") or "") != text:
                final_cleanup_ok = cleanup_owned_temp(output, published.get("output_identity"))
                result["temp_cleanup_success"] = bool(result["temp_cleanup_success"]) and final_cleanup_ok
                return _fail(result, "lyrics_verification_failed", "发布后 LRC 内容校验失败。")
            result.update({
                "success": True,
                "message": "已安全另存新的 UTF-8 LRC 文件；原始歌词文件未修改。",
                "verification_success": True,
                "encoding": "UTF-8（无 BOM）",
                "sourceUnchanged": True,
            })
            return result
        except OSError as exc:
            return _fail_with_cleanup(result, temp_path, temp_identity, "lrc_temp_write_failed", f"LRC 临时写入失败：{exc}")
        except Exception as exc:
            return _fail_with_cleanup(result, temp_path, temp_identity, "lrc_temp_write_failed", f"LRC 导出异常：{exc}")

    def _validate_paths(self, request: EditExportRequest):
        raw_source = str(request.source_path or "").strip()
        raw_output = str(request.output_path or "").strip()
        if not raw_source:
            return None, None, ("source_missing", "源文件路径为空。")
        if not raw_output:
            return None, None, ("output_required", "必须手动选择全新输出路径。")
        try:
            source = Path(raw_source).expanduser().resolve()
            output = Path(raw_output).expanduser().resolve()
        except OSError as exc:
            return None, None, ("source_missing", f"无法规范化路径：{exc}")
        if not source.is_file():
            return None, None, ("source_missing", "源文件不存在或不是普通文件。")
        if _same_path(source, output):
            return None, None, ("output_same_as_source", "输出路径不能是源文件本身。")
        if source.suffix.lower() != output.suffix.lower():
            return None, None, ("output_extension_mismatch", "输出文件扩展名必须与源文件一致。")
        if output.exists():
            return None, None, ("output_exists", "输出路径已存在，系统不会覆盖已有文件。")
        return source, output, None

    def _validate_operations(self, source: Path, request: EditExportRequest, operations: tuple[str, ...]):
        extension = source.suffix.lower()
        if request.cover_action not in {"keep", "replace", "remove"}:
            return "cover_write_failed", "封面操作仅支持 keep、replace 或 remove。"
        if "metadata" in operations and extension not in _METADATA_WRITE_EXTENSIONS:
            return "source_unsupported", "当前格式不支持写入文件信息。"
        if "cover" in operations:
            if extension not in _COVER_WRITE_EXTENSIONS:
                return "source_unsupported", "当前格式不支持写入封面。"
            if request.cover_action == "replace" and (not request.cover_data or request.cover_mime not in {"image/jpeg", "image/png"}):
                return "cover_write_failed", "替换封面仅支持非空 JPEG 或 PNG 数据。"
            if request.cover_action == "replace":
                cover_validation = validate_cover_bytes(request.cover_data or b"")
                if not cover_validation.get("ok"):
                    return (
                        str(cover_validation.get("error_code") or "cover_write_failed"),
                        str(cover_validation.get("message") or "封面图片验证失败。"),
                    )
                if cover_validation.get("mime") != request.cover_mime:
                    return "cover_write_failed", "封面 MIME 与实际图片格式不一致。"
        if "lyrics" in operations:
            if extension not in _LYRICS_WRITE_EXTENSIONS:
                return "source_unsupported", "当前格式不支持写入内嵌歌词。"
        return None

    def _apply_operations(self, temp_path: Path, request: EditExportRequest, operations: tuple[str, ...]):
        if "metadata" in operations:
            applied = write_audio_metadata(str(temp_path), request.metadata_changes or {}, overwrite=True)
            if not applied.get("success"):
                return "metadata_write_failed", str(applied.get("error") or "文件信息写入失败。")
        if "cover" in operations:
            if request.cover_action == "replace":
                applied = write_audio_cover(str(temp_path), request.cover_data, request.cover_mime)
            else:
                applied = remove_audio_cover(str(temp_path))
            if not applied.get("success"):
                return "cover_write_failed", str(applied.get("error") or "封面写入失败。")
        if "lyrics" in operations:
            if str(request.lyrics_text or "").strip():
                applied = embed_lrc_to_audio(
                    str(temp_path),
                    str(request.lyrics_text),
                    overwrite=True,
                )
                if not applied.get("embedded"):
                    return "lyrics_write_failed", str(
                        applied.get("error") or "内嵌歌词写入失败。"
                    )
            else:
                applied = remove_embedded_lyrics(str(temp_path))
                if not applied.get("removed"):
                    return "lyrics_write_failed", str(
                        applied.get("error") or "内嵌歌词移除失败。"
                    )
        return None

    def _verify(self, path: Path, request: EditExportRequest, operations: tuple[str, ...]):
        if not path.is_file() or path.stat().st_size <= 0:
            return "verification_failed", "编辑副本不存在或内容为空。"
        metadata = read_audio_metadata(str(path), include_cover=False)
        if not metadata.get("ok", metadata.get("success", False)):
            return "verification_failed", "无法重新读取编辑副本的文件信息。"
        if "metadata" in operations:
            for field, expected in (request.metadata_changes or {}).items():
                actual = _metadata_value(metadata, field)
                if str(actual or "") != str(expected or ""):
                    return "verification_failed", f"文件信息字段校验失败：{field}。"
        if "cover" in operations:
            cover = read_cover_preview(str(path))
            if not cover.get("ok", cover.get("success", False)):
                return "verification_failed", "无法重新读取编辑副本的封面。"
            expected_cover = request.cover_action == "replace"
            if bool(cover.get("has_cover")) != expected_cover:
                return "verification_failed", "封面状态与请求不一致。"
            if expected_cover:
                cover_metadata = read_audio_metadata(str(path), include_cover=True)
                extracted = bytes(cover_metadata.get("cover_data") or b"")
                if not cover_metadata.get("ok", cover_metadata.get("success", False)) or not extracted:
                    return "verification_failed", "无法读取编辑副本中的封面数据。"
                actual = validate_cover_bytes(extracted)
                if not actual.get("ok"):
                    return "verification_failed", "编辑副本中的封面图片无法验证。"
                expected = validate_cover_bytes(request.cover_data or b"")
                if (
                    not expected.get("ok")
                    or actual.get("mime") != expected.get("mime")
                    or actual.get("width") != expected.get("width")
                    or actual.get("height") != expected.get("height")
                    or sha256(extracted).hexdigest() != sha256(bytes(request.cover_data or b"")).hexdigest()
                ):
                    return "verification_failed", "编辑副本中的封面与草稿不一致。"
        if "lyrics" in operations:
            lyrics = read_embedded_lyrics(str(path))
            if (
                not lyrics.get("ok")
                or str(lyrics.get("lyrics_text") or "") != str(request.lyrics_text or "")
            ):
                return "verification_failed", "内嵌歌词与请求不一致。"
        return None


def supported_edit_modules(path: str) -> list[str]:
    extension = Path(str(path or "")).suffix.lower()
    modules: list[str] = []
    if extension in _METADATA_WRITE_EXTENSIONS:
        modules.append("metadata")
    if extension in _LYRICS_WRITE_EXTENSIONS:
        modules.append("lyrics")
    if extension in _COVER_WRITE_EXTENSIONS:
        modules.append("cover")
    return modules


def _required_capabilities(operations: tuple[str, ...]) -> tuple[str, ...]:
    mapping = {"metadata": METADATA_WRITE, "lyrics": LYRICS_WRITE, "cover": COVER_WRITE}
    return tuple(mapping[operation] for operation in operations)


def _metadata_value(result: dict, field: str):
    for key in _METADATA_ALIASES.get(field, (field,)):
        if key in result:
            return result.get(key)
    return None


def _merged_metadata_changes(source: Path, requested: dict[str, str]):
    source_metadata = read_audio_metadata(str(source), include_cover=False)
    if not source_metadata.get("ok", source_metadata.get("success", False)):
        return None, (
            "verification_failed",
            "无法读取源文件信息，已拒绝创建可能清空标签的编辑副本。",
        )

    merged = {
        field: str(_metadata_value(source_metadata, field) or "").strip()
        for field in _METADATA_FIELDS
    }
    for requested_field, value in requested.items():
        field = _METADATA_INPUT_ALIASES.get(requested_field, requested_field)
        if field not in _METADATA_FIELDS:
            return None, ("metadata_write_failed", f"不支持导出文件信息字段：{requested_field}。")
        merged[field] = str(value or "").strip()
    return merged, None


def _same_path(first: Path, second: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(first))) == os.path.normcase(os.path.normpath(str(second)))


def _make_temp_path(output: Path) -> Path:
    return output.parent / f".{output.stem}.cherryq_edit_{uuid4().hex}.tmp{output.suffix}"


def _identity(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
        return stat.st_dev, stat.st_ino
    except OSError:
        return None


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _base_result(request: EditExportRequest) -> dict[str, object]:
    return {
        "success": False,
        "error_code": "",
        "message": "",
        "source_path": str(request.source_path or ""),
        "output_path": str(request.output_path or ""),
        "required_capabilities": [],
        "applied_operations": [],
        "finalization_strategy": "",
        "temp_cleanup_success": True,
        "verification_success": False,
        "warnings": [],
        "appliedModules": [],
        "skippedModules": [],
        "failedModules": [],
        "sourceUnchanged": True,
    }


def _base_lrc_result(request: LrcExportRequest) -> dict[str, object]:
    return {
        "success": False,
        "error_code": "",
        "message": "",
        "source_path": str(request.source_path or ""),
        "output_path": str(request.output_path or ""),
        "required_capabilities": [LYRICS_WRITE],
        "applied_operations": ["lrc"],
        "finalization_strategy": "",
        "temp_cleanup_success": True,
        "verification_success": False,
        "warnings": [],
        "encoding": "UTF-8（无 BOM）",
        "appliedModules": ["lrc"],
        "skippedModules": [],
        "failedModules": [],
        "sourceUnchanged": True,
    }


def _fail(result: dict[str, object], code: str, message: str) -> dict[str, object]:
    result["error_code"] = code
    result["message"] = message
    if result.get("appliedModules") and code not in {
        "output_exists",
        "output_conflict",
    }:
        result["failedModules"] = list(result.get("appliedModules") or [])
    return result


def _fail_with_cleanup(
    result: dict[str, object],
    temp_path: Path,
    identity: tuple[int, int] | None,
    code: str,
    message: str,
) -> dict[str, object]:
    result["temp_cleanup_success"] = cleanup_owned_temp(temp_path, identity)
    return _fail(result, code, message)


def _cancelled(request: EditExportRequest | LrcExportRequest) -> bool:
    event = request.cancel_event
    return bool(event is not None and event.is_set())


def _cancelled_result(result: dict[str, object]) -> dict[str, object]:
    return _fail(result, "export_cancelled", "导出已取消；未发布正式输出。")


def _cancelled_with_cleanup(
    result: dict[str, object],
    temp_path: Path,
    identity: tuple[int, int] | None,
) -> dict[str, object]:
    result["temp_cleanup_success"] = cleanup_owned_temp(temp_path, identity)
    return _cancelled_result(result)

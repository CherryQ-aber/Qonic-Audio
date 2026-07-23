import filecmp
import os
import re
import shutil

from logger import logger

try:
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, ID3NoHeaderError, USLT
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis
except ImportError:  # pragma: no cover - runtime dependency guard
    FLAC = None
    ID3 = None
    ID3NoHeaderError = Exception
    MP4 = None
    OggOpus = None
    OggVorbis = None
    USLT = None


LRC_EXTENSIONS = (".lrc", ".LRC")
LRC_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "latin-1")
LYRICS_COMMENT_KEYS = ("lyrics", "unsyncedlyrics")
LRC_PREVIEW_ENCODINGS = ("utf-8-sig", "utf-8", "gbk")
LRC_TIMESTAMP_RE = re.compile(
    r"^\s*(?:\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\])+\s*.*$"
)
SUPPORTED_EMBEDDED_LYRICS_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".mp4", ".aac"}
)


def _mutagen_available():
    return all((FLAC, ID3, MP4, OggVorbis, USLT))


def _iter_unique_paths(paths):
    seen = set()

    for path in paths:
        if not path:
            continue

        normalized = os.path.normcase(os.path.abspath(os.path.normpath(path)))

        if normalized in seen:
            continue

        seen.add(normalized)
        yield os.path.abspath(os.path.normpath(path))


def _lrc_candidates_for_source(source_path):
    base_path, _extension = os.path.splitext(source_path)

    for lrc_extension in LRC_EXTENSIONS:
        yield base_path + lrc_extension


def find_matching_lrc(source_path, extra_source_paths=None):
    search_paths = [source_path]
    search_paths.extend(extra_source_paths or [])

    for current_source_path in _iter_unique_paths(search_paths):
        for candidate in _lrc_candidates_for_source(current_source_path):
            if os.path.isfile(candidate):
                logger.info(f"找到同名歌词文件: {candidate}")
                return candidate

    logger.info(f"未找到同名歌词文件，跳过歌词处理: {source_path}")
    return None


def read_lrc_file(lrc_path):
    for encoding in LRC_ENCODINGS:
        try:
            with open(lrc_path, "r", encoding=encoding) as file_obj:
                return file_obj.read()
        except UnicodeDecodeError:
            continue
        except OSError as e:
            logger.warning(f"歌词文件读取失败: {lrc_path} - {e}")
            return None

    logger.warning(f"歌词文件编码无法识别，已跳过: {lrc_path}")
    return None


def read_lrc_file_preview(lrc_path):
    """Read an external LRC into memory without retaining a write target."""
    normalized_path = os.fspath(lrc_path) if lrc_path else ""
    result = {
        "ok": False,
        "error": "",
        "source": "external_lrc_preview",
        "path": normalized_path,
        "filename": os.path.basename(normalized_path),
        "has_lyrics": False,
        "lyrics_text": "",
        "line_count": 0,
        "has_timestamps": False,
        "encoding": "",
        "is_memory_preview": True,
    }

    if not normalized_path:
        result["error"] = "路径为空"
        return result

    if os.path.splitext(normalized_path)[1].lower() != ".lrc":
        result["error"] = "仅支持 .lrc 文件"
        return result

    if not os.path.isfile(normalized_path):
        result["error"] = "LRC 文件不存在"
        return result

    for encoding in LRC_PREVIEW_ENCODINGS:
        try:
            with open(normalized_path, "r", encoding=encoding) as file_obj:
                text = file_obj.read()
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            result["error"] = f"LRC 读取失败：{exc}"
            return result

        result["ok"] = True
        result["lyrics_text"] = text
        result["has_lyrics"] = bool(text.strip())
        result["line_count"] = len(text.splitlines())
        result["has_timestamps"] = _lyrics_text_has_timestamps(text)
        result["encoding"] = encoding
        return result

    result["error"] = "LRC 编码无法识别（支持 UTF-8、UTF-8 BOM、GBK）"
    return result


def write_lrc_file(lrc_path, text, encoding="utf-8-sig"):
    output_path = os.path.abspath(os.path.normpath(lrc_path))
    output_dir = os.path.dirname(output_path)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding=encoding) as file_obj:
        file_obj.write(text)


def _has_comment_lyrics(audio):
    if not audio:
        return False

    for key in LYRICS_COMMENT_KEYS:
        values = audio.get(key) or audio.get(key.upper())

        if values:
            return True

    return False


def _audio_format_label(audio_path):
    return os.path.splitext(audio_path)[1].lstrip(".").upper() or "-"


def _format_lyrics_value(value):
    if value is None:
        return ""

    if hasattr(value, "text"):
        return _format_lyrics_value(value.text)

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    if isinstance(value, (list, tuple)):
        parts = [_format_lyrics_value(item) for item in value]
        parts = [part for part in parts if part]
        return "\n".join(parts).strip()

    return str(value).strip()


def _get_comment_value(audio, key):
    for candidate in (key, key.lower(), key.upper()):
        try:
            value = audio.get(candidate)
        except Exception:
            value = None

        if value:
            return value

    wanted = key.lower()

    try:
        items = audio.items()
    except Exception:
        return None

    for existing_key, value in items:
        if str(existing_key).lower() == wanted and value:
            return value

    return None


def _read_comment_lyrics(audio):
    detected_fields = []
    lyrics_text = ""

    for key in ("LYRICS", "UNSYNCEDLYRICS"):
        value = _get_comment_value(audio, key)
        if value:
            detected_fields.append(key)
        text = _format_lyrics_value(value)
        if text and not lyrics_text:
            lyrics_text = text

    return lyrics_text, detected_fields


def _read_mp3_lyrics(audio_path):
    try:
        tags = ID3(audio_path)
    except ID3NoHeaderError:
        return "", []

    lyrics_text = ""
    detected_fields = []

    for key, frame in tags.items():
        frame_id = str(
            getattr(frame, "FrameID", "") or str(key).split(":", 1)[0]
        ).upper()
        field_name = ""

        if frame_id == "USLT":
            field_name = "USLT"
        elif frame_id == "SYLT":
            field_name = "SYLT"
        elif frame_id == "TXXX":
            description = str(getattr(frame, "desc", "") or "").strip().upper()
            if description in {"LYRICS", "UNSYNCEDLYRICS"}:
                field_name = f"TXXX:{description}"

        if not field_name:
            continue
        if field_name not in detected_fields:
            detected_fields.append(field_name)

        # SYLT is detected but intentionally not decoded in Phase 4.3A.
        if field_name == "SYLT":
            continue
        text = _format_lyrics_value(frame)
        if text and not lyrics_text:
            lyrics_text = text

    return lyrics_text, detected_fields


def read_embedded_lyrics(audio_path):
    normalized_path = os.fspath(audio_path) if audio_path else ""
    result = {
        "ok": False,
        "error": "",
        "source": "embedded",
        "path": normalized_path,
        "filename": os.path.basename(normalized_path),
        "has_lyrics": False,
        "lyrics_text": "",
        "line_count": 0,
        "has_timestamps": False,
        "detected_fields": [],
        "read_backend": "mutagen",
        "found": False,
        "lyrics": "",
        "source_type": None,
        "format": _audio_format_label(normalized_path),
        "field": None,
    }

    if not normalized_path:
        result["error"] = "路径为空"
        return result

    if not os.path.isfile(normalized_path):
        result["error"] = "音频文件不存在"
        return result

    extension = os.path.splitext(normalized_path)[1].lower()
    if extension not in SUPPORTED_EMBEDDED_LYRICS_EXTENSIONS:
        result["error"] = f"不支持的歌词读取格式：{extension or '无扩展名'}"
        return result

    required_backend = {
        ".mp3": ID3,
        ".flac": FLAC,
        ".ogg": OggVorbis,
        ".opus": OggOpus,
        ".m4a": MP4,
        ".mp4": MP4,
        ".aac": MP4,
    }.get(extension)
    if required_backend is None:
        message = "mutagen 未安装，无法读取真实内嵌歌词"
        logger.warning(message)
        result["error"] = message
        return result

    try:
        if extension == ".mp3":
            lyrics_text, detected_fields = _read_mp3_lyrics(normalized_path)
        elif extension == ".flac":
            lyrics_text, detected_fields = _read_comment_lyrics(
                FLAC(normalized_path)
            )
        elif extension == ".ogg":
            lyrics_text, detected_fields = _read_comment_lyrics(
                OggVorbis(normalized_path)
            )
        elif extension == ".opus":
            lyrics_text, detected_fields = _read_comment_lyrics(
                OggOpus(normalized_path)
            )
        elif extension in (".m4a", ".mp4", ".aac"):
            value = MP4(normalized_path).get("\xa9lyr")
            lyrics_text = _format_lyrics_value(value)
            detected_fields = ["©lyr"] if value else []
        else:
            return result

        result["ok"] = True
        result["detected_fields"] = detected_fields
        result["has_lyrics"] = bool(lyrics_text or detected_fields)
        if lyrics_text:
            result["lyrics_text"] = lyrics_text
            result["line_count"] = len(lyrics_text.splitlines())
            result["has_timestamps"] = _lyrics_text_has_timestamps(
                lyrics_text
            )
            result["found"] = True
            result["lyrics"] = lyrics_text
            result["source_type"] = "embedded"
            result["field"] = (
                detected_fields[0] if detected_fields else None
            )
            logger.info(
                f"已读取音频内嵌歌词: {normalized_path} "
                f"({', '.join(detected_fields)})"
            )
        elif detected_fields:
            logger.info(
                f"已检测到音频歌词字段但正文解析暂缓: {normalized_path} "
                f"({', '.join(detected_fields)})"
            )
        else:
            logger.info(f"当前音频未检测到内嵌歌词: {normalized_path}")

        return result

    except Exception as e:
        message = f"mutagen 歌词读取失败：{e}"
        logger.warning(f"内嵌歌词读取失败: {normalized_path} - {message}")
        result["error"] = message
        return result


def _lyrics_text_has_timestamps(text):
    return any(LRC_TIMESTAMP_RE.match(line) for line in str(text or "").splitlines())


def audio_has_lyrics(audio_path):
    if not _mutagen_available():
        logger.warning("未安装 mutagen，无法检查音频歌词标签")
        return False

    extension = os.path.splitext(audio_path)[1].lower()

    try:
        if extension == ".mp3":
            try:
                tags = ID3(audio_path)
            except ID3NoHeaderError:
                return False

            return any(
                frame_id.startswith(("USLT", "SYLT"))
                for frame_id in tags.keys()
            )

        if extension == ".flac":
            return _has_comment_lyrics(FLAC(audio_path))

        if extension == ".ogg":
            return _has_comment_lyrics(OggVorbis(audio_path))

        if extension == ".opus":
            if OggOpus is None:
                return False
            return _has_comment_lyrics(OggOpus(audio_path))

        if extension in (".m4a", ".mp4", ".aac"):
            audio = MP4(audio_path)
            return bool(audio.get("\xa9lyr"))

        return False

    except Exception as e:
        logger.warning(f"读取音频歌词标签失败，按无歌词处理: {audio_path} - {e}")
        return False


def _embed_mp3_lyrics(audio_path, lrc_text, overwrite):
    try:
        tags = ID3(audio_path)
    except ID3NoHeaderError:
        tags = ID3()

    if overwrite:
        tags.delall("USLT")
        tags.delall("SYLT")

    tags.add(USLT(encoding=3, lang="und", desc="", text=lrc_text))
    tags.save(audio_path)


def _embed_comment_lyrics(audio, lrc_text):
    audio["LYRICS"] = [lrc_text]
    audio["UNSYNCEDLYRICS"] = [lrc_text]
    audio.save()


def embed_lrc_to_audio(audio_path, lrc_text, overwrite=False):
    result = {
        "embedded": False,
        "skipped_reason": None,
        "error": None,
    }

    extension = os.path.splitext(audio_path)[1].lower()

    if extension == ".wav":
        logger.info("当前格式暂不支持写入内嵌歌词: WAV")
        result["skipped_reason"] = "unsupported_wav"
        return result

    if not _mutagen_available():
        message = "未安装 mutagen，无法写入内嵌歌词"
        logger.warning(message)
        result["error"] = message
        return result

    try:
        if not overwrite and audio_has_lyrics(audio_path):
            logger.info(f"目标音频已存在歌词，已跳过写入: {audio_path}")
            result["skipped_reason"] = "already_has_lyrics"
            return result

        if extension == ".mp3":
            _embed_mp3_lyrics(audio_path, lrc_text, overwrite)
        elif extension == ".flac":
            _embed_comment_lyrics(FLAC(audio_path), lrc_text)
        elif extension == ".ogg":
            _embed_comment_lyrics(OggVorbis(audio_path), lrc_text)
        elif extension == ".opus":
            if OggOpus is None:
                raise RuntimeError("当前 mutagen 环境不支持 OPUS 歌词写入")
            _embed_comment_lyrics(OggOpus(audio_path), lrc_text)
        elif extension in (".m4a", ".mp4", ".aac"):
            audio = MP4(audio_path)
            audio["\xa9lyr"] = [lrc_text]
            audio.save()
        else:
            logger.info(
                f"当前格式暂不支持写入内嵌歌词: {extension.lstrip('.').upper()}"
            )
            result["skipped_reason"] = "unsupported_format"
            return result

        logger.info(f"已写入内嵌歌词: {audio_path}")
        result["embedded"] = True
        return result

    except Exception as e:
        logger.warning(f"内嵌歌词写入失败，已跳过: {audio_path} - {e}")
        result["error"] = str(e)
        return result


def remove_embedded_lyrics(audio_path):
    """Remove embedded lyrics from an edited copy."""
    result = {
        "removed": False,
        "skipped_reason": None,
        "error": None,
    }
    extension = os.path.splitext(audio_path)[1].lower()
    if extension not in SUPPORTED_EMBEDDED_LYRICS_EXTENSIONS:
        result["skipped_reason"] = "unsupported_format"
        return result
    if not _mutagen_available():
        result["error"] = "未安装 mutagen，无法移除内嵌歌词"
        return result

    try:
        if extension == ".mp3":
            try:
                tags = ID3(audio_path)
            except ID3NoHeaderError:
                tags = ID3()
            tags.delall("USLT")
            tags.delall("SYLT")
            tags.save(audio_path)
        elif extension == ".flac":
            _remove_comment_lyrics(FLAC(audio_path))
        elif extension == ".ogg":
            _remove_comment_lyrics(OggVorbis(audio_path))
        elif extension == ".opus":
            if OggOpus is None:
                raise RuntimeError("当前 mutagen 环境不支持 OPUS 歌词移除")
            _remove_comment_lyrics(OggOpus(audio_path))
        else:
            audio = MP4(audio_path)
            if "\xa9lyr" in audio:
                del audio["\xa9lyr"]
            audio.save()
        result["removed"] = True
        return result
    except Exception as exc:
        logger.warning(f"内嵌歌词移除失败: {audio_path} - {exc}")
        result["error"] = str(exc)
        return result


def _remove_comment_lyrics(audio):
    tags = getattr(audio, "tags", None)
    if tags is not None:
        for key in list(tags.keys()):
            if str(key).lower() in {
                "lyrics",
                "unsyncedlyrics",
                "syncedlyrics",
            }:
                del tags[key]
    audio.save()


def _available_lrc_output_path(output_lrc_path, source_lrc_path):
    if not os.path.exists(output_lrc_path):
        return output_lrc_path

    try:
        if filecmp.cmp(source_lrc_path, output_lrc_path, shallow=False):
            return output_lrc_path
    except OSError:
        pass

    output_dir = os.path.dirname(output_lrc_path)
    stem, extension = os.path.splitext(os.path.basename(output_lrc_path))
    suffix = 1

    while True:
        candidate = os.path.join(output_dir, f"{stem} ({suffix}){extension}")

        if not os.path.exists(candidate):
            return candidate

        try:
            if filecmp.cmp(source_lrc_path, candidate, shallow=False):
                return candidate
        except OSError:
            pass

        suffix += 1


def copy_lrc_to_output(lrc_path, output_audio_path):
    result = {
        "copied": False,
        "output_lrc_path": None,
        "skipped_reason": None,
        "error": None,
    }

    try:
        output_dir = os.path.dirname(output_audio_path)
        output_stem = os.path.splitext(os.path.basename(output_audio_path))[0]
        output_lrc_path = os.path.join(output_dir, f"{output_stem}.lrc")
        target_path = _available_lrc_output_path(output_lrc_path, lrc_path)

        if os.path.exists(target_path):
            logger.info(f"输出目录已存在相同歌词文件，已跳过复制: {target_path}")
            result["output_lrc_path"] = target_path
            result["skipped_reason"] = "same_file_exists"
            return result

        shutil.copy2(lrc_path, target_path)
        logger.info(f"已复制外置歌词到输出目录: {target_path}")
        result["copied"] = True
        result["output_lrc_path"] = target_path
        return result

    except Exception as e:
        logger.warning(f"外置歌词复制失败，已跳过: {lrc_path} - {e}")
        result["error"] = str(e)
        return result


def process_lyrics_for_output(
    source_path,
    output_audio_path,
    extra_source_paths=None,
    embed=True,
    copy_external=True,
    overwrite=False,
):
    summary = {
        "found": False,
        "lrc_path": None,
        "embedded": False,
        "copied": False,
        "copied_path": None,
        "skipped_reason": None,
        "error": None,
    }

    lrc_path = find_matching_lrc(source_path, extra_source_paths)

    if not lrc_path:
        summary["skipped_reason"] = "not_found"
        return summary

    summary["found"] = True
    summary["lrc_path"] = lrc_path

    if not copy_external and not embed:
        logger.info("歌词文件存在，但歌词处理选项均未开启，已跳过")
        summary["skipped_reason"] = "options_disabled"
        return summary

    if not copy_external and embed:
        logger.info("已关闭外置 .lrc 复制，仅处理内嵌歌词")

    lrc_text = read_lrc_file(lrc_path)

    if lrc_text is None:
        summary["skipped_reason"] = "read_failed"
        return summary

    if copy_external:
        copy_result = copy_lrc_to_output(lrc_path, output_audio_path)
        summary["copied"] = copy_result.get("copied", False)
        summary["copied_path"] = copy_result.get("output_lrc_path")

    if embed:
        embed_result = embed_lrc_to_audio(
            output_audio_path,
            lrc_text,
            overwrite=overwrite,
        )
        summary["embedded"] = embed_result.get("embedded", False)

        if embed_result.get("skipped_reason"):
            summary["skipped_reason"] = embed_result["skipped_reason"]

        if embed_result.get("error"):
            summary["error"] = embed_result["error"]

    if summary["embedded"] and not copy_external:
        logger.info("已写入内嵌歌词，未复制外置 .lrc")
    elif summary["copied"] and not embed:
        logger.info("已复制外置 .lrc，未写入内嵌歌词")

    return summary

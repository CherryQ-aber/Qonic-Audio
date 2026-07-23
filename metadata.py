import base64
from datetime import datetime
import io
import os

try:
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import (
        APIC,
        COMM,
        ID3,
        ID3NoHeaderError,
        TALB,
        TBPM,
        TCON,
        TDRC,
        TIT2,
        TKEY,
        TPE1,
        TPE2,
        TPOS,
        TRCK,
    )
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis
except ImportError:  # pragma: no cover - runtime dependency guard
    MutagenFile = None
    FLAC = None
    ID3 = None
    ID3NoHeaderError = None
    COMM = None
    TALB = None
    TBPM = None
    TCON = None
    TDRC = None
    TIT2 = None
    TKEY = None
    TPE1 = None
    TPE2 = None
    TPOS = None
    TRCK = None
    MP4 = None
    Picture = None
    MP4Cover = None
    OggOpus = None
    OggVorbis = None


TEXT_TAG_KEYS = {
    "title": ("title", "TIT2", "\xa9nam"),
    "artist": ("artist", "TPE1", "\xa9ART", "aART"),
    "album": ("album", "TALB", "\xa9alb"),
    "albumartist": ("albumartist", "album_artist", "TPE2", "aART"),
    "date": ("date", "year", "TDRC", "TYER", "\xa9day"),
    "genre": ("genre", "TCON", "\xa9gen"),
    "tracknumber": ("tracknumber", "track", "TRCK", "trkn"),
    "discnumber": ("discnumber", "disc", "TPOS", "disk"),
    "bpm": ("bpm", "TBPM", "tmpo"),
    "initialkey": ("initialkey", "key", "TKEY", "\xa9key"),
    "comment": ("comment", "description", "COMM", "\xa9cmt", "desc"),
}

EDITABLE_METADATA_FIELDS = (
    "title",
    "artist",
    "album",
    "albumartist",
    "date",
    "genre",
    "tracknumber",
    "discnumber",
    "bpm",
    "initialkey",
    "comment",
)

COMMENT_TAG_KEYS = {
    "title": "title",
    "artist": "artist",
    "album": "album",
    "albumartist": "albumartist",
    "date": "date",
    "genre": "genre",
    "tracknumber": "tracknumber",
    "discnumber": "discnumber",
    "bpm": "bpm",
    "initialkey": "initialkey",
    "comment": "comment",
}

MP4_TAG_KEYS = {
    "title": "\xa9nam",
    "artist": "\xa9ART",
    "album": "\xa9alb",
    "albumartist": "aART",
    "date": "\xa9day",
    "genre": "\xa9gen",
    "initialkey": "\xa9key",
    "comment": "\xa9cmt",
}

SUPPORTED_METADATA_READ_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".wav",
        ".aiff",
        ".aif",
        ".ape",
        ".wma",
    }
)

DEFAULT_COVER_PREVIEW_SIZE = 512
MAX_COVER_RAW_BYTES = 10 * 1024 * 1024
MAX_COVER_DATA_URL_BYTES = 2 * 1024 * 1024


def read_audio_metadata(audio_path, *, include_cover=True):
    normalized_path = os.fspath(audio_path) if audio_path else ""
    extension_with_dot = os.path.splitext(normalized_path)[1].lower()
    result = {
        "ok": False,
        "success": False,
        "path": normalized_path,
        "filename": os.path.basename(normalized_path),
        "format": extension_with_dot.lstrip(".").upper() or "-",
        "extension": extension_with_dot.lstrip("."),
        "container_format": extension_with_dot.lstrip(".").upper() or "-",
        "title": "",
        "artist": "",
        "album": "",
        "albumartist": "",
        "album_artist": "",
        "date": "",
        "year": "",
        "genre": "",
        "tracknumber": "",
        "track": "",
        "discnumber": "",
        "disc": "",
        "bpm": "",
        "initialkey": "",
        "comment": "",
        "duration": None,
        "duration_seconds": None,
        "duration_text": "-",
        "sample_rate": None,
        "sample_rate_text": "-",
        "bitrate": None,
        "bitrate_text": "-",
        "channels": None,
        "channels_text": "-",
        "bits_per_sample": None,
        "codec": "",
        "file_size": None,
        "file_size_text": "-",
        "modified_time": None,
        "cover_data": None,
        "cover_mime": None,
        "cover_source": "",
        "has_basic_tags": False,
        "has_cover": False,
        "has_lyrics": False,
        "read_backend": "mutagen",
        "error": "",
    }

    if not normalized_path:
        result["error"] = "路径为空"
        return result

    if not os.path.isfile(normalized_path):
        result["error"] = "文件不存在"
        return result

    try:
        result["file_size"] = os.path.getsize(normalized_path)
        result["modified_time"] = os.path.getmtime(normalized_path)
        result["file_size_text"] = format_file_size(result["file_size"])
    except OSError as exc:
        result["error"] = f"无法读取文件信息：{exc}"
        return result

    if MutagenFile is None:
        result["error"] = "mutagen 未安装，无法读取真实 metadata"
        return result

    try:
        audio = MutagenFile(normalized_path)
    except Exception as e:
        result["error"] = f"mutagen 读取失败：{e}"
        return result

    if audio is None:
        result["error"] = "不支持的格式或文件损坏"
        return result

    info = getattr(audio, "info", None)

    if info is not None:
        result["duration"] = getattr(info, "length", None)
        result["duration_seconds"] = result["duration"]
        result["sample_rate"] = getattr(info, "sample_rate", None)
        result["bitrate"] = getattr(info, "bitrate", None)
        result["channels"] = getattr(info, "channels", None)
        result["bits_per_sample"] = (
            getattr(info, "bits_per_sample", None)
            or getattr(info, "sample_size", None)
        )
        result["codec"] = (
            getattr(info, "codec", None)
            or getattr(info, "codec_description", None)
            or getattr(info, "encoder_info", None)
            or type(info).__name__
        )
        result["duration_text"] = format_duration(result["duration"])
        result["bitrate_text"] = format_bitrate(result["bitrate"])
        if result["sample_rate"]:
            try:
                result["sample_rate_text"] = (
                    f"{int(result['sample_rate'])} Hz"
                )
            except (TypeError, ValueError):
                result["sample_rate_text"] = "-"
        if result["channels"]:
            result["channels_text"] = str(result["channels"])

    for field, keys in TEXT_TAG_KEYS.items():
        result[field] = _read_first_tag(audio, keys)

    result["album_artist"] = result["albumartist"]
    result["year"] = result["date"]
    result["track"] = result["tracknumber"]
    result["disc"] = result["discnumber"]
    result["has_basic_tags"] = any(
        result.get(field)
        for field in (
            "title",
            "artist",
            "album",
            "albumartist",
            "date",
            "genre",
            "tracknumber",
            "discnumber",
            "comment",
        )
    )
    result["has_cover"] = has_embedded_cover(audio)
    result["has_lyrics"] = has_embedded_lyrics(audio)

    if include_cover:
        cover_data, cover_mime, cover_source = extract_cover_info(audio)
        result["cover_data"] = cover_data
        result["cover_mime"] = cover_mime
        result["cover_source"] = cover_source

    result["ok"] = True
    result["success"] = True
    return result


def read_cover_preview(file_path: str, max_size: int = DEFAULT_COVER_PREVIEW_SIZE) -> dict:
    """Read an embedded cover as a bounded in-memory preview for QML.

    This function is intentionally read-only: it never calls mutagen save,
    never writes image bytes to disk, and never returns the original binary
    object to QML.
    """

    normalized_path = os.fspath(file_path) if file_path else ""
    result = {
        "ok": False,
        "success": False,
        "error": "",
        "path": normalized_path,
        "filename": os.path.basename(normalized_path),
        "has_cover": False,
        "mime": "",
        "width": 0,
        "height": 0,
        "byte_size": 0,
        "byte_size_text": "-",
        "dimensions_text": "-",
        "preview_data_url": "",
        "cover_source": "",
        "read_backend": "mutagen",
    }

    if not normalized_path:
        result["error"] = "路径为空"
        return result

    if not os.path.isfile(normalized_path):
        result["error"] = "文件不存在"
        return result

    if MutagenFile is None:
        result["error"] = "mutagen 未安装，无法读取真实封面"
        return result

    try:
        audio = MutagenFile(normalized_path)
    except Exception as exc:
        result["error"] = f"mutagen 读取失败：{exc}"
        return result

    if audio is None:
        result["error"] = "不支持的格式或文件损坏"
        return result

    try:
        cover_data, cover_mime, cover_source = extract_cover_info(audio)
    except Exception as exc:
        result["error"] = f"封面读取失败：{exc}"
        return result

    if not cover_data:
        result.update(
            {
                "ok": True,
                "success": True,
                "error": "",
                "has_cover": False,
            }
        )
        return result

    cover_bytes = bytes(cover_data)
    byte_size = len(cover_bytes)
    mime = _normalize_preview_mime(cover_mime)
    result.update(
        {
            "ok": True,
            "success": True,
            "has_cover": True,
            "mime": mime,
            "byte_size": byte_size,
            "byte_size_text": format_file_size(byte_size),
            "cover_source": cover_source or "embedded",
        }
    )

    if byte_size > MAX_COVER_RAW_BYTES:
        result["error"] = "检测到封面，但图片过大，已跳过预览。"
        return result

    preview = _build_cover_preview_data_url(cover_bytes, mime, max_size)
    result.update(
        {
            "preview_data_url": preview["data_url"],
            "mime": preview["mime"] or mime,
            "width": preview["width"],
            "height": preview["height"],
            "dimensions_text": (
                f"{preview['width']} x {preview['height']}"
                if preview["width"] and preview["height"]
                else "-"
            ),
        }
    )

    if preview["error"]:
        result["error"] = preview["error"]

    return result


def read_audio_cover_preview(audio_path):
    result = {
        "success": False,
        "cover_data": None,
        "cover_mime": None,
        "error": None,
    }

    if MutagenFile is None:
        result["error"] = "未安装 mutagen，无法读取封面。"
        return result

    try:
        audio = MutagenFile(audio_path)
    except Exception as e:
        result["error"] = str(e)
        return result

    if audio is None:
        result["error"] = "不支持的格式或文件损坏"
        return result

    cover_data, cover_mime, _cover_source = extract_cover_info(audio)
    result["success"] = True
    result["cover_data"] = cover_data
    result["cover_mime"] = cover_mime
    return result


def write_audio_metadata(audio_path, metadata, overwrite=True):
    if MutagenFile is None:
        return {"success": False, "error": "未安装 mutagen，无法写入音频信息。"}

    ext = os.path.splitext(audio_path)[1].lower()
    values = _normalize_editable_metadata(metadata or {})

    try:
        if ext == ".mp3":
            if ID3 is None:
                return {"success": False, "error": "当前环境不支持写入 MP3 ID3 标签。"}
            _write_mp3_metadata(audio_path, values)
            return {"success": True, "error": None}

        if ext == ".flac":
            if FLAC is None:
                return {"success": False, "error": "当前环境不支持写入 FLAC 标签。"}
            audio = FLAC(audio_path)
            _write_comment_metadata(audio, values)
            audio.save()
            return {"success": True, "error": None}

        if ext in (".m4a", ".mp4", ".aac"):
            if MP4 is None:
                return {"success": False, "error": "当前环境不支持写入 M4A/MP4 标签。"}
            audio = MP4(audio_path)
            _write_mp4_metadata(audio, values)
            audio.save()
            return {"success": True, "error": None}

        if ext == ".ogg":
            if OggVorbis is None:
                return {"success": False, "error": "当前环境不支持写入 OGG 标签。"}
            audio = OggVorbis(audio_path)
            _write_comment_metadata(audio, values)
            audio.save()
            return {"success": True, "error": None}

        if ext == ".opus":
            if OggOpus is None:
                return {"success": False, "error": "当前环境不支持写入 OPUS 标签。"}
            audio = OggOpus(audio_path)
            _write_comment_metadata(audio, values)
            audio.save()
            return {"success": True, "error": None}

        if ext == ".wav":
            return {"success": False, "error": "当前格式暂不支持写入音频信息。"}

        return {"success": False, "error": "当前格式暂不支持写入音频信息。"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def write_audio_cover(audio_path, cover_data, cover_mime):
    if MutagenFile is None:
        return {"success": False, "error": "未安装 mutagen，无法写入封面。"}

    if not cover_data:
        return {"success": False, "error": "没有可写入的封面数据。"}

    cover_mime = _normalize_cover_mime(cover_mime)

    if cover_mime not in ("image/jpeg", "image/png"):
        return {"success": False, "error": "当前仅支持写入 JPEG 或 PNG 封面。"}

    ext = os.path.splitext(audio_path)[1].lower()

    try:
        if ext == ".mp3":
            _write_mp3_cover(audio_path, cover_data, cover_mime)
            return {"success": True, "error": None}

        if ext == ".flac":
            _write_flac_cover(audio_path, cover_data, cover_mime)
            return {"success": True, "error": None}

        if ext in (".m4a", ".mp4", ".aac"):
            _write_mp4_cover(audio_path, cover_data, cover_mime)
            return {"success": True, "error": None}

        if ext == ".ogg":
            _write_comment_cover(OggVorbis(audio_path), cover_data, cover_mime)
            return {"success": True, "error": None}

        if ext == ".opus":
            if OggOpus is None:
                raise RuntimeError("当前环境不支持写入 OPUS 封面。")
            _write_comment_cover(OggOpus(audio_path), cover_data, cover_mime)
            return {"success": True, "error": None}

        return {"success": False, "error": "当前格式暂不支持写入封面。"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def remove_audio_cover(audio_path):
    if MutagenFile is None:
        return {"success": False, "error": "未安装 mutagen，无法移除封面。"}

    ext = os.path.splitext(audio_path)[1].lower()

    try:
        if ext == ".mp3":
            _remove_mp3_cover(audio_path)
            return {"success": True, "error": None}

        if ext == ".flac":
            _remove_flac_cover(audio_path)
            return {"success": True, "error": None}

        if ext in (".m4a", ".mp4", ".aac"):
            _remove_mp4_cover(audio_path)
            return {"success": True, "error": None}

        if ext == ".ogg":
            _remove_comment_cover(OggVorbis(audio_path))
            return {"success": True, "error": None}

        if ext == ".opus":
            if OggOpus is None:
                raise RuntimeError("当前环境不支持移除 OPUS 封面。")
            _remove_comment_cover(OggOpus(audio_path))
            return {"success": True, "error": None}

        return {"success": False, "error": "当前格式暂不支持写入封面。"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_audio_cover(source_audio_path, target_audio_path):
    metadata = read_audio_metadata(source_audio_path)

    if not metadata.get("success"):
        return {
            "success": False,
            "copied": False,
            "error": metadata.get("error") or "源音频封面读取失败。",
        }

    cover_data = metadata.get("cover_data")
    cover_mime = metadata.get("cover_mime")

    if not cover_data:
        return {"success": True, "copied": False, "error": None}

    result = write_audio_cover(target_audio_path, cover_data, cover_mime)

    if result.get("success"):
        return {"success": True, "copied": True, "error": None}

    return {
        "success": False,
        "copied": False,
        "error": result.get("error") or "封面复制失败。",
    }


def extract_cover_data(audio):
    cover_data, cover_mime, _cover_source = extract_cover_info(audio)
    return cover_data, cover_mime


def has_embedded_cover(audio):
    """Return only a cover-presence flag without copying image bytes."""
    if audio is None:
        return False

    if getattr(audio, "pictures", None):
        return True

    tags = getattr(audio, "tags", None)
    if not tags:
        return False

    try:
        items = tags.items()
    except AttributeError:
        return False

    for key, value in items:
        normalized = str(key).strip().lower()
        if (
            normalized == "covr"
            or normalized.startswith("apic")
            or normalized in {
                "metadata_block_picture",
                "coverart",
            }
        ) and bool(value):
            return True
    return False


def has_embedded_lyrics(audio):
    """Return only a lyrics-presence flag without reading lyric content."""
    tags = getattr(audio, "tags", None) if audio is not None else None
    if not tags:
        return False

    try:
        items = tags.items()
    except AttributeError:
        return False

    lyric_keys = {
        "lyrics",
        "unsyncedlyrics",
        "syncedlyrics",
        "©lyr",
    }
    for key, value in items:
        normalized = str(key).strip().lower()
        if (
            normalized in lyric_keys
            or normalized.startswith("uslt")
            or normalized.startswith("sylt")
        ) and bool(value):
            return True
    return False


def extract_cover_info(audio):
    if audio is None:
        return None, None, ""

    if getattr(audio, "pictures", None):
        picture = audio.pictures[0]
        return getattr(picture, "data", None), getattr(picture, "mime", None), "FLAC picture"

    tags = getattr(audio, "tags", None)

    if not tags:
        return None, None, ""

    if "covr" in tags:
        covers = tags.get("covr") or []
        if covers:
            cover = covers[0]
            mime = "image/jpeg"

            if MP4Cover is not None and getattr(cover, "imageformat", None) == MP4Cover.FORMAT_PNG:
                mime = "image/png"

            return bytes(cover), mime, "MP4 covr"

    for key, value in tags.items():
        if str(key).startswith("APIC"):
            return getattr(value, "data", None), getattr(value, "mime", None), str(key)

    picture_values = tags.get("metadata_block_picture") or tags.get("METADATA_BLOCK_PICTURE")
    if picture_values and Picture is not None:
        for value in _ensure_iterable(picture_values):
            try:
                picture = Picture(base64.b64decode(value))
                return picture.data, picture.mime, "METADATA_BLOCK_PICTURE"
            except Exception:
                continue

    coverart_values = tags.get("coverart") or tags.get("COVERART")
    if coverart_values:
        mime_values = tags.get("coverartmime") or tags.get("COVERARTMIME") or ["image/jpeg"]
        mime = _format_tag_value(mime_values) or "image/jpeg"
        for value in _ensure_iterable(coverart_values):
            try:
                return base64.b64decode(value), mime, "coverart"
            except Exception:
                continue

    return None, None, ""


def _normalize_preview_mime(mime):
    normalized = _normalize_cover_mime(mime)
    if normalized in {"image/jpeg", "image/png"}:
        return normalized
    if normalized in {"image/webp", "image/gif"}:
        return normalized
    return "image/jpeg"


def _build_cover_preview_data_url(cover_bytes, mime, max_size):
    max_px = _normalize_preview_size(max_size)
    width, height = _sniff_image_size(cover_bytes, mime)

    try:
        from PIL import Image
    except Exception:
        return _build_raw_cover_data_url(
            cover_bytes,
            mime,
            width,
            height,
            "当前缺少 Pillow，已使用原始封面小图预览。"
            if len(cover_bytes) <= MAX_COVER_DATA_URL_BYTES
            else "当前缺少 Pillow，封面过大，已跳过预览。",
        )

    try:
        with Image.open(io.BytesIO(cover_bytes)) as image:
            width, height = image.size
            preview_image = image.copy()
            resample = getattr(Image, "Resampling", Image).LANCZOS
            preview_image.thumbnail((max_px, max_px), resample)

            output_mime = "image/png" if _has_alpha(preview_image) else "image/jpeg"
            output = io.BytesIO()
            if output_mime == "image/jpeg":
                if preview_image.mode not in ("RGB", "L"):
                    background = Image.new("RGB", preview_image.size, (255, 255, 255))
                    if preview_image.mode in ("RGBA", "LA"):
                        background.paste(
                            preview_image.convert("RGBA"),
                            mask=preview_image.convert("RGBA").split()[-1],
                        )
                    else:
                        background.paste(preview_image.convert("RGB"))
                    preview_image = background
                preview_image.save(
                    output,
                    format="JPEG",
                    quality=85,
                    optimize=True,
                )
            else:
                preview_image.save(output, format="PNG", optimize=True)

            preview_bytes = output.getvalue()
            data_url = _cover_data_url(preview_bytes, output_mime)
            if len(data_url.encode("ascii")) > MAX_COVER_DATA_URL_BYTES:
                return {
                    "data_url": "",
                    "mime": output_mime,
                    "width": width,
                    "height": height,
                    "error": "检测到封面，但预览 data URL 超过安全大小，已跳过预览。",
                }
            return {
                "data_url": data_url,
                "mime": output_mime,
                "width": width,
                "height": height,
                "error": "",
            }
    except Exception as exc:
        fallback = _build_raw_cover_data_url(
            cover_bytes,
            mime,
            width,
            height,
            f"Pillow 无法解析封面，已尝试原始小图预览：{exc}",
        )
        if fallback["data_url"]:
            return fallback
        return {
            "data_url": "",
            "mime": mime,
            "width": width,
            "height": height,
            "error": f"封面预览生成失败：{exc}",
        }


def _build_raw_cover_data_url(cover_bytes, mime, width, height, message):
    if len(cover_bytes) > MAX_COVER_DATA_URL_BYTES:
        return {
            "data_url": "",
            "mime": mime,
            "width": width,
            "height": height,
            "error": message,
        }

    data_url = _cover_data_url(cover_bytes, mime)
    if len(data_url.encode("ascii")) > MAX_COVER_DATA_URL_BYTES:
        return {
            "data_url": "",
            "mime": mime,
            "width": width,
            "height": height,
            "error": message,
        }

    return {
        "data_url": data_url,
        "mime": mime,
        "width": width,
        "height": height,
        "error": "" if "已使用原始封面小图预览" in message else message,
    }


def _cover_data_url(image_bytes, mime):
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime or 'image/jpeg'};base64,{encoded}"


def _normalize_preview_size(max_size):
    try:
        value = int(max_size)
    except (TypeError, ValueError):
        value = DEFAULT_COVER_PREVIEW_SIZE
    return max(64, min(value, 1024))


def _has_alpha(image):
    if image.mode in ("RGBA", "LA"):
        return True
    if image.mode == "P":
        return "transparency" in getattr(image, "info", {})
    return False


def _sniff_image_size(data, mime):
    if not data:
        return 0, 0

    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")

    if data.startswith(b"\xff\xd8"):
        return _sniff_jpeg_size(data)

    return 0, 0


def _sniff_jpeg_size(data):
    index = 2
    length = len(data)
    start_of_frame_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }

    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        while index < length and data[index] == 0xFF:
            index += 1
        if index >= length:
            break
        marker = data[index]
        index += 1
        if marker in (0xD8, 0xD9):
            continue
        if index + 2 > length:
            break
        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > length:
            break
        if marker in start_of_frame_markers and segment_length >= 7:
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height
        index += segment_length

    return 0, 0


def format_duration(seconds):
    if seconds is None:
        return "-"

    try:
        total_seconds = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "-"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def format_file_size(size_bytes):
    if size_bytes is None:
        return "-"

    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "-"

    units = ("B", "KB", "MB", "GB")
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"

    return f"{size:.2f} {units[unit_index]}"


def format_bitrate(bitrate):
    if not bitrate:
        return "-"

    try:
        return f"{int(round(float(bitrate) / 1000))} kbps"
    except (TypeError, ValueError):
        return "-"


def format_sample_rate(sample_rate):
    if not sample_rate:
        return "-"

    try:
        value = float(sample_rate) / 1000
    except (TypeError, ValueError):
        return "-"

    if value.is_integer():
        return f"{int(value)} kHz"

    return f"{value:.1f} kHz"


def format_bit_depth(bits_per_sample):
    if not bits_per_sample:
        return "-"

    try:
        return f"{int(bits_per_sample)} bit"
    except (TypeError, ValueError):
        return "-"


def format_modified_time(timestamp):
    if timestamp is None:
        return "-"

    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return "-"


def _read_first_tag(audio, keys):
    tags = getattr(audio, "tags", None)

    if not tags:
        return ""

    for key in keys:
        value = _get_tag_value(tags, key)

        if value is None:
            continue

        if key == "trkn":
            return _format_mp4_track(value)

        formatted = _format_tag_value(value)

        if formatted:
            return formatted

    return ""


def _get_tag_value(tags, key):
    for candidate in (key, str(key).lower(), str(key).upper()):
        try:
            value = tags.get(candidate)
        except Exception:
            value = None

        if value is not None:
            return value

    wanted = str(key).lower()

    try:
        items = tags.items()
    except Exception:
        return None

    for existing_key, value in items:
        if str(existing_key).lower() == wanted:
            return value

    return None


def _format_mp4_track(value):
    values = _ensure_iterable(value)

    if not values:
        return ""

    first = values[0]

    if isinstance(first, (tuple, list)) and first:
        track = first[0]
        total = first[1] if len(first) > 1 else 0
        return f"{track}/{total}" if total else str(track)

    return _format_tag_value(first)


def _format_tag_value(value):
    if value is None:
        return ""

    if hasattr(value, "text"):
        return _format_tag_value(value.text)

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return ""

    if isinstance(value, (list, tuple)):
        parts = [_format_tag_value(item) for item in value]
        parts = [part for part in parts if part]
        return " / ".join(parts)

    return str(value)


def _ensure_iterable(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        return list(value)

    return [value]


def _normalize_editable_metadata(metadata):
    values = {}

    for field in EDITABLE_METADATA_FIELDS:
        value = metadata.get(field, "")

        if value is None or value == "-":
            value = ""

        values[field] = str(value).strip()

    return values


def _write_mp3_metadata(audio_path, values):
    try:
        tags = ID3(audio_path)
    except Exception as e:
        if ID3NoHeaderError is not None and isinstance(e, ID3NoHeaderError):
            tags = ID3()
        else:
            raise

    _set_id3_text(tags, "TIT2", TIT2, values["title"])
    _set_id3_text(tags, "TPE1", TPE1, values["artist"])
    _set_id3_text(tags, "TALB", TALB, values["album"])
    _set_id3_text(tags, "TDRC", TDRC, values["date"])
    _set_id3_text(tags, "TCON", TCON, values["genre"])
    _set_id3_text(tags, "TRCK", TRCK, values["tracknumber"])
    _set_id3_text(tags, "TPE2", TPE2, values["albumartist"])
    _set_id3_text(tags, "TPOS", TPOS, values["discnumber"])
    _set_id3_text(tags, "TBPM", TBPM, values["bpm"])
    _set_id3_text(tags, "TKEY", TKEY, values["initialkey"])
    _set_id3_comment(tags, values["comment"])
    tags.save(audio_path)


def _set_id3_text(tags, frame_id, frame_class, value):
    tags.delall(frame_id)

    if not value:
        return

    tags.add(frame_class(encoding=3, text=value))


def _set_id3_comment(tags, value):
    tags.delall("COMM")

    if not value:
        return

    tags.add(COMM(encoding=3, lang="eng", desc="", text=value))


def _write_comment_metadata(audio, values):
    for field, key in COMMENT_TAG_KEYS.items():
        value = values[field]

        if value:
            audio[key] = [value]
        elif key in audio:
            del audio[key]


def _write_mp4_metadata(audio, values):
    for field, key in MP4_TAG_KEYS.items():
        value = values[field]

        if value:
            audio[key] = [value]
        elif key in audio:
            del audio[key]

    _set_mp4_tuple_tag(audio, "trkn", values["tracknumber"])
    _set_mp4_tuple_tag(audio, "disk", values["discnumber"])
    _set_mp4_int_tag(audio, "tmpo", values["bpm"])


def _set_mp4_tuple_tag(audio, key, value):
    parsed = _parse_mp4_track(value)

    if parsed is None:
        if key in audio:
            del audio[key]
        return

    audio[key] = [parsed]


def _set_mp4_int_tag(audio, key, value):
    if not value:
        if key in audio:
            del audio[key]
        return

    try:
        audio[key] = [int(float(str(value).strip()))]
    except (TypeError, ValueError):
        if key in audio:
            del audio[key]


def _parse_mp4_track(value):
    if not value:
        return None

    parts = str(value).split("/", 1)

    try:
        track = int(parts[0].strip())
        total = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0
    except (TypeError, ValueError):
        return None

    return (track, total)



def _normalize_cover_mime(cover_mime):
    normalized = str(cover_mime or "").lower().strip()

    if normalized in ("image/jpg", "jpg", "jpeg", "image/jpeg"):
        return "image/jpeg"

    if normalized in ("png", "image/png"):
        return "image/png"

    return normalized


def _load_id3_tags_for_write(audio_path):
    try:
        return ID3(audio_path)
    except Exception as e:
        if ID3NoHeaderError is not None and isinstance(e, ID3NoHeaderError):
            return ID3()
        raise


def _load_existing_id3_tags(audio_path):
    try:
        return ID3(audio_path)
    except Exception as e:
        if ID3NoHeaderError is not None and isinstance(e, ID3NoHeaderError):
            return None
        raise


def _write_mp3_cover(audio_path, cover_data, cover_mime):
    if ID3 is None or APIC is None:
        raise RuntimeError("当前环境不支持写入 MP3 封面。")

    tags = _load_id3_tags_for_write(audio_path)
    tags.delall("APIC")
    tags.add(APIC(
        encoding=3,
        mime=cover_mime,
        type=3,
        desc="Cover",
        data=cover_data,
    ))
    tags.save(audio_path)


def _remove_mp3_cover(audio_path):
    if ID3 is None:
        raise RuntimeError("当前环境不支持移除 MP3 封面。")

    tags = _load_existing_id3_tags(audio_path)

    if tags is None:
        return

    tags.delall("APIC")
    tags.save(audio_path)


def _write_flac_cover(audio_path, cover_data, cover_mime):
    if FLAC is None or Picture is None:
        raise RuntimeError("当前环境不支持写入 FLAC 封面。")

    audio = FLAC(audio_path)
    audio.clear_pictures()
    picture = Picture()
    picture.type = 3
    picture.mime = cover_mime
    picture.desc = "Cover"
    picture.data = cover_data
    audio.add_picture(picture)
    audio.save()

def _remove_flac_cover(audio_path):
    if FLAC is None:
        raise RuntimeError("当前环境不支持移除 FLAC 封面。")

    audio = FLAC(audio_path)
    audio.clear_pictures()
    audio.save()


def _write_mp4_cover(audio_path, cover_data, cover_mime):
    if MP4 is None or MP4Cover is None:
        raise RuntimeError("当前环境不支持写入 M4A/MP4 封面。")

    image_format = MP4Cover.FORMAT_PNG if cover_mime == "image/png" else MP4Cover.FORMAT_JPEG
    audio = MP4(audio_path)
    audio["covr"] = [MP4Cover(cover_data, imageformat=image_format)]
    audio.save()


def _remove_mp4_cover(audio_path):
    if MP4 is None:
        raise RuntimeError("当前环境不支持移除 M4A/MP4 封面。")

    audio = MP4(audio_path)

    if "covr" in audio:
        del audio["covr"]

    audio.save()


def _write_comment_cover(audio, cover_data, cover_mime):
    if Picture is None:
        raise RuntimeError("当前环境不支持写入 OGG/OPUS 封面。")
    picture = Picture()
    picture.type = 3
    picture.mime = cover_mime
    picture.desc = "Cover"
    picture.data = bytes(cover_data)
    _remove_comment_cover_keys(audio)
    audio["metadata_block_picture"] = [
        base64.b64encode(picture.write()).decode("ascii")
    ]
    audio.save()


def _remove_comment_cover(audio):
    _remove_comment_cover_keys(audio)
    audio.save()


def _remove_comment_cover_keys(audio):
    tags = getattr(audio, "tags", None)
    if tags is None:
        return
    for key in list(tags.keys()):
        if str(key).lower() in {
            "metadata_block_picture",
            "coverart",
            "coverartmime",
        }:
            del tags[key]

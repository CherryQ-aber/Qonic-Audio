from __future__ import annotations

import base64
from io import BytesIO
from typing import Any
import warnings

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - the runtime dependency is pinned
    Image = None
    UnidentifiedImageError = Exception


MAX_COVER_FILE_BYTES = 15 * 1024 * 1024
MAX_COVER_WIDTH = 10_000
MAX_COVER_HEIGHT = 10_000
MAX_COVER_PIXELS = 40_000_000
MAX_PREVIEW_EDGE = 512
MAX_PREVIEW_DATA_URL_BYTES = 2 * 1024 * 1024

_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png"}


def validate_cover_bytes(data: bytes, *, enforce_size_limit: bool = True) -> dict[str, Any]:
    """Validate a JPEG/PNG cover and prepare a bounded in-memory preview."""
    raw = bytes(data or b"")
    if not raw:
        return _failure("cover_decode_failed", "封面图片数据为空。")
    if enforce_size_limit and len(raw) > MAX_COVER_FILE_BYTES:
        return _failure("cover_file_too_large", "封面图片超过 15 MB 限制。")
    if Image is None:
        return _failure("cover_decode_failed", "Pillow 不可用，无法验证封面图片。")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as probe:
                image_format = str(probe.format or "").upper()
                if image_format not in _FORMAT_TO_MIME:
                    return _failure("cover_format_unsupported", "封面仅支持 JPEG 或 PNG 图片。")
                if getattr(probe, "n_frames", 1) != 1:
                    return _failure("cover_format_unsupported", "不支持动画封面图片。")
                width, height = probe.size
                dimension_error = _validate_dimensions(width, height)
                if dimension_error:
                    return dimension_error
                probe.verify()

            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                preview_url = _build_preview(decoded, image_format)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return _failure("cover_decode_failed", "封面图片无法解码。")
    except Image.DecompressionBombWarning:
        return _failure("cover_pixel_limit_exceeded", "封面图片像素总量超过限制。")

    return {
        "ok": True,
        "error_code": "",
        "message": "封面图片验证通过。",
        "data": raw,
        "mime": _FORMAT_TO_MIME[image_format],
        "width": int(width),
        "height": int(height),
        "byte_size": len(raw),
        "preview_data_url": preview_url,
    }


def read_and_validate_cover_file(path: str) -> dict[str, Any]:
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_COVER_FILE_BYTES + 1)
    except FileNotFoundError:
        return _failure("cover_file_missing", "选择的封面文件不存在。")
    except OSError as exc:
        return _failure("cover_file_missing", f"无法读取封面文件：{exc}")
    return validate_cover_bytes(data)


def _validate_dimensions(width: int, height: int) -> dict[str, Any] | None:
    if width <= 0 or height <= 0:
        return _failure("cover_dimensions_invalid", "封面图片尺寸无效。")
    if width > MAX_COVER_WIDTH or height > MAX_COVER_HEIGHT:
        return _failure("cover_dimensions_too_large", "封面图片边长超过 10,000 px 限制。")
    if width * height > MAX_COVER_PIXELS:
        return _failure("cover_pixel_limit_exceeded", "封面图片像素总量超过限制。")
    return None


def _build_preview(image, image_format: str) -> str:
    preview = image.copy()
    preview.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE))
    output = BytesIO()
    if image_format == "JPEG":
        if preview.mode not in {"RGB", "L"}:
            preview = preview.convert("RGB")
        preview.save(output, format="JPEG", quality=88, optimize=True)
    else:
        preview.save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    data_url = f"data:{_FORMAT_TO_MIME[image_format]};base64,{encoded}"
    if len(data_url.encode("ascii")) > MAX_PREVIEW_DATA_URL_BYTES:
        return ""
    return data_url


def _failure(error_code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
        "data": b"",
        "mime": "",
        "width": 0,
        "height": 0,
        "byte_size": 0,
        "preview_data_url": "",
    }

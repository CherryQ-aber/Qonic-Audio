import os


SUPPORTED_INPUT_EXTENSIONS = {
    ".ncm": "NCM",
    ".mp3": "MP3",
    ".flac": "FLAC",
    ".wav": "WAV",
    ".m4a": "M4A",
    ".aac": "AAC",
    ".ogg": "OGG",
    ".opus": "OPUS",
    ".ape": "APE",
    ".aiff": "AIFF",
    ".aif": "AIFF",
    ".wma": "WMA",
}

EDITOR_AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".ape",
    ".aiff",
    ".aif",
    ".alac",
    ".wma",
}

SUPPORTED_TARGET_FORMATS = {
    "mp3": {
        "label": "MP3",
        "extension": ".mp3",
        "description": "通用有损格式",
        "ffmpeg_args": [],
    },
    "flac": {
        "label": "FLAC",
        "extension": ".flac",
        "description": "无损压缩格式",
        "ffmpeg_args": [],
    },
    "wav": {
        "label": "WAV",
        "extension": ".wav",
        "description": "无压缩音频格式",
        "ffmpeg_args": [],
    },
    "aac": {
        "label": "AAC",
        "extension": ".aac",
        "description": "AAC 音频流",
        "ffmpeg_args": [],
    },
    "m4a": {
        "label": "M4A",
        "extension": ".m4a",
        "description": "M4A/AAC 容器",
        "ffmpeg_args": ["-c:a", "aac"],
    },
    "ogg": {
        "label": "OGG",
        "extension": ".ogg",
        "description": "OGG/Vorbis 容器",
        "ffmpeg_args": [],
    },
    "opus": {
        "label": "OPUS",
        "extension": ".opus",
        "description": "Opus 音频格式",
        "ffmpeg_args": [],
    },
}

IGNORED_EXTENSIONS = {
    ".lrc",
    ".txt",
}

DEFAULT_TARGET_FORMAT = "flac"


def normalize_extension(path_or_ext):
    value = os.fspath(path_or_ext or "").strip()

    if not value:
        return ""

    if value.startswith(".") and os.path.basename(value) == value:
        extension = value
    else:
        extension = os.path.splitext(value)[1]

    return extension.lower()


def get_source_format(path):
    extension = normalize_extension(path)
    return SUPPORTED_INPUT_EXTENSIONS.get(extension, extension.lstrip(".").upper())


def is_supported_input_file(path):
    return normalize_extension(path) in SUPPORTED_INPUT_EXTENSIONS


def is_supported_editor_audio_file(path):
    return normalize_extension(path) in EDITOR_AUDIO_EXTENSIONS


def get_editor_audio_filter():
    extensions = " ".join(f"*{extension}" for extension in sorted(EDITOR_AUDIO_EXTENSIONS))
    return f"普通音频文件 ({extensions});;所有文件 (*.*)"


def is_ignored_file(path):
    return normalize_extension(path) in IGNORED_EXTENSIONS


def normalize_target_format(format_name, default=None):
    normalized = str(format_name or "").strip().lower()

    if normalized in SUPPORTED_TARGET_FORMATS:
        return normalized

    return default


def is_supported_target_format(format_name):
    return normalize_target_format(format_name) is not None


def get_target_format_options():
    return list(SUPPORTED_TARGET_FORMATS.keys())


def get_target_extension(format_name):
    normalized = normalize_target_format(format_name, DEFAULT_TARGET_FORMAT)
    return SUPPORTED_TARGET_FORMATS[normalized]["extension"]


def get_target_label(format_name):
    normalized = normalize_target_format(format_name, DEFAULT_TARGET_FORMAT)
    return SUPPORTED_TARGET_FORMATS[normalized]["label"]


def get_ffmpeg_args_for_target(format_name):
    normalized = normalize_target_format(format_name, DEFAULT_TARGET_FORMAT)
    return list(SUPPORTED_TARGET_FORMATS[normalized].get("ffmpeg_args", []))

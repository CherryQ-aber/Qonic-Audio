import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone


DIRTY_LABELS = {
    "metadata": "元数据",
    "cover": "封面",
    "lyrics": "歌词",
    "pitch": "升降调",
    "audio_content": "音频内容",
    "format": "导出格式",
}


def _normalize_path(path):
    return os.path.normpath(os.path.abspath(path))


def _file_signature(file_path):
    normalized = _normalize_path(file_path)

    try:
        stat_result = os.stat(normalized)
        size = stat_result.st_size
        modified = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1000000000))
    except OSError:
        size = 0
        modified = 0

    return f"{normalized}|{size}|{modified}"


def workspace_key_for_file(file_path):
    return hashlib.sha1(_file_signature(file_path).encode("utf-8", errors="ignore")).hexdigest()[:20]


def workspace_root(editor_temp_folder):
    return os.path.join(_normalize_path(editor_temp_folder), "Workspaces")


def workspace_dir_for_file(editor_temp_folder, file_path):
    return os.path.join(workspace_root(editor_temp_folder), workspace_key_for_file(file_path))


@dataclass
class AudioEditWorkspace:
    source_file_path: str
    workspace_dir: str
    working_audio_path: str = ""
    has_unsaved_changes: bool = False
    dirty_flags: set = field(default_factory=set)
    pending_metadata: dict = field(default_factory=dict)
    pending_cover: dict = field(default_factory=dict)
    pending_lyrics: dict = field(default_factory=dict)
    pending_audio_process: dict = field(default_factory=dict)
    export_history: list = field(default_factory=list)
    last_export_path: str = ""
    target_export_format: str = "original"

    @classmethod
    def create(cls, source_file_path, editor_temp_folder):
        source = _normalize_path(source_file_path)
        workspace_dir = workspace_dir_for_file(editor_temp_folder, source)
        state = cls(source_file_path=source, workspace_dir=workspace_dir)
        state.ensure_directories()
        state.write_source_info()
        return state

    @property
    def pending_changes_path(self):
        return os.path.join(self.workspace_dir, "pending_changes.json")

    @property
    def export_dir(self):
        return os.path.join(self.workspace_dir, "export")

    @property
    def backup_dir(self):
        editor_temp_root = os.path.dirname(os.path.dirname(self.workspace_dir))
        return os.path.join(editor_temp_root, "Backups", os.path.basename(self.workspace_dir))

    def ensure_directories(self):
        for folder in (
            self.workspace_dir,
            self.export_dir,
            self.backup_dir,
            os.path.join(self.workspace_dir, "preview"),
            os.path.join(self.workspace_dir, "cover"),
            os.path.join(self.workspace_dir, "lyrics"),
        ):
            os.makedirs(folder, exist_ok=True)

    def write_source_info(self):
        self.ensure_directories()
        info_path = os.path.join(self.workspace_dir, "source_info.json")
        payload = {
            "source_file_path": self.source_file_path,
            "workspace_dir": self.workspace_dir,
            "created_or_seen_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(info_path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def dirty_labels(self):
        ordered = ("metadata", "cover", "lyrics", "pitch", "audio_content", "format")
        labels = [
            DIRTY_LABELS.get(flag, flag)
            for flag in ordered
            if flag in self.dirty_flags and not (flag == "audio_content" and "pitch" in self.dirty_flags)
        ]
        unknown_flags = [
            flag
            for flag in sorted(self.dirty_flags)
            if flag not in DIRTY_LABELS
        ]

        if unknown_flags:
            labels.append("其他修改")

        return labels

    def unknown_dirty_flags(self):
        return [
            flag
            for flag in sorted(self.dirty_flags)
            if flag not in DIRTY_LABELS
        ]

    def mark_dirty(self, flag, pending=None):
        self.ensure_directories()
        self.dirty_flags.add(flag)
        self.has_unsaved_changes = True

        if flag == "metadata":
            self.pending_metadata = dict(pending or {})
        elif flag == "cover":
            self.pending_cover = dict(pending or {})
        elif flag == "lyrics":
            self.pending_lyrics = dict(pending or {})
        elif flag in ("pitch", "audio_content"):
            merged = dict(self.pending_audio_process or {})
            merged.update(pending or {})
            self.pending_audio_process = merged
        elif flag == "format":
            self.target_export_format = str((pending or {}).get("target_format") or "original")

        self.save_pending_changes()

    def save_pending_changes(self):
        if not self.has_unsaved_changes:
            self.remove_pending_changes()
            return

        self.ensure_directories()
        payload = self.to_pending_dict()

        with open(self.pending_changes_path, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    def remove_pending_changes(self):
        try:
            if os.path.isfile(self.pending_changes_path):
                os.remove(self.pending_changes_path)
        except OSError:
            pass

    def clear_changes(self, remove_pending=True):
        self.has_unsaved_changes = False
        self.dirty_flags.clear()
        self.pending_metadata = {}
        self.pending_cover = {}
        self.pending_lyrics = {}
        self.pending_audio_process = {}
        self.target_export_format = "original"

        if remove_pending:
            self.remove_pending_changes()

    def clear_dirty_flag(self, flag):
        self.dirty_flags.discard(flag)

        if flag == "metadata":
            self.pending_metadata = {}
        elif flag == "cover":
            self.pending_cover = {}
        elif flag == "lyrics":
            self.pending_lyrics = {}
        elif flag in ("pitch", "audio_content"):
            self.pending_audio_process = {}
            self.dirty_flags.discard("pitch")
            self.dirty_flags.discard("audio_content")
        elif flag == "format":
            self.target_export_format = "original"

        self.has_unsaved_changes = bool(self.dirty_flags)
        self.save_pending_changes()

    def mark_exported(self, output_path):
        normalized_output = _normalize_path(output_path)
        self.last_export_path = normalized_output
        self.export_history.append({
            "output_path": normalized_output,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        })
        self.clear_changes(remove_pending=True)

    def discard(self, remove_workspace=False):
        self.clear_changes(remove_pending=True)

        if remove_workspace:
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

    def to_pending_dict(self):
        return {
            "source_file_path": self.source_file_path,
            "working_audio_path": self.working_audio_path,
            "workspace_dir": self.workspace_dir,
            "has_unsaved_changes": self.has_unsaved_changes,
            "dirty_flags": sorted(self.dirty_flags),
            "pending_metadata": self.pending_metadata,
            "pending_cover": self.pending_cover,
            "pending_lyrics": self.pending_lyrics,
            "pending_audio_process": self.pending_audio_process,
            "export_history": self.export_history,
            "last_export_path": self.last_export_path,
            "target_export_format": self.target_export_format,
            "last_modified": datetime.now(timezone.utc).isoformat(),
        }

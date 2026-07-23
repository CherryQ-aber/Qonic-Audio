import hashlib
import os
import tempfile
import unittest
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ui_next.bridge.capabilities import (
    AUDIO_EXPORT,
    AUDIO_PROCESSING,
    COVER_WRITE,
    LYRICS_WRITE,
    METADATA_WRITE,
    CapabilityGate,
)
from ui_next.bridge.edit_export_service import (
    EditExportRequest,
    EditExportService,
    LrcExportRequest,
)


class EditExportServiceTests(unittest.TestCase):
    @staticmethod
    def _png_bytes() -> bytes:
        image = Image.new("RGB", (4, 3), (20, 40, 60))
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def _source(self, root, name="source.flac"):
        path = root / name
        path.write_bytes(b"original-audio-bytes")
        return path

    def _sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _service_with_backend(self, capabilities):
        state = {"metadata": {}, "cover": False, "cover_data": b"", "cover_mime": "", "lyrics": ""}

        def metadata_write(_path, values, overwrite=True):
            state["metadata"].update(values)
            return {"success": True}

        def cover_write(_path, data, mime):
            state["cover"] = True
            state["cover_data"] = bytes(data)
            state["cover_mime"] = mime
            return {"success": True}

        def cover_remove(_path):
            state["cover"] = False
            state["cover_data"] = b""
            state["cover_mime"] = ""
            return {"success": True}

        def lyrics_write(_path, text, overwrite=True):
            state["lyrics"] = text
            return {"embedded": True}

        def metadata_read(path, include_cover=False):
            result = {"ok": True, "path": path, **state["metadata"]}
            if include_cover:
                result.update({"cover_data": state["cover_data"], "cover_mime": state["cover_mime"]})
            return result

        def cover_read(_path):
            return {"ok": True, "has_cover": state["cover"]}

        def lyrics_read(_path):
            return {"ok": True, "has_lyrics": bool(state["lyrics"]), "lyrics_text": state["lyrics"]}

        stack = ExitStack()
        stack.enter_context(patch("ui_next.bridge.edit_export_service.write_audio_metadata", side_effect=metadata_write))
        stack.enter_context(patch("ui_next.bridge.edit_export_service.write_audio_cover", side_effect=cover_write))
        stack.enter_context(patch("ui_next.bridge.edit_export_service.remove_audio_cover", side_effect=cover_remove))
        stack.enter_context(patch("ui_next.bridge.edit_export_service.embed_lrc_to_audio", side_effect=lyrics_write))
        stack.enter_context(patch("ui_next.bridge.edit_export_service.read_audio_metadata", side_effect=metadata_read))
        stack.enter_context(patch("ui_next.bridge.edit_export_service.read_cover_preview", side_effect=cover_read))
        stack.enter_context(patch("ui_next.bridge.edit_export_service.read_embedded_lyrics", side_effect=lyrics_read))
        return EditExportService(CapabilityGate(capabilities)), state, stack

    def test_no_changes_and_missing_capability_create_no_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "edited.flac"
            result = EditExportService(CapabilityGate((METADATA_WRITE,))).export(EditExportRequest(str(source), str(output)))
            self.assertEqual("no_changes", result["error_code"])
            self.assertFalse(output.exists())

            with patch("ui_next.bridge.edit_export_service.shutil.copy2") as copy:
                denied = EditExportService(CapabilityGate()).export(EditExportRequest(str(source), str(output), metadata_changes={"title": "Draft"}))
            self.assertEqual("capability_denied", denied["error_code"])
            copy.assert_not_called()

    def test_path_validation_rejects_empty_same_extension_mismatch_and_existing_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            service = EditExportService(CapabilityGate((METADATA_WRITE,)))
            request = lambda output: EditExportRequest(str(source), output, metadata_changes={"title": "Draft"})
            self.assertEqual("output_required", service.export(request("")).get("error_code"))
            self.assertEqual("overwrite_confirmation_required", service.export(request(str(source))).get("error_code"))
            self.assertEqual("output_extension_mismatch", service.export(request(str(root / "edited.mp3"))).get("error_code"))
            existing = root / "existing.flac"
            existing.write_bytes(b"keep")
            before = existing.read_bytes()
            self.assertEqual("overwrite_confirmation_required", service.export(request(str(existing))).get("error_code"))
            self.assertEqual(before, existing.read_bytes())

    def test_metadata_lyrics_cover_replace_and_remove_publish_new_copy(self):
        capabilities = (METADATA_WRITE, LYRICS_WRITE, COVER_WRITE)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            source_hash = self._sha(source)
            output = root / "edited.flac"
            service, state, stack = self._service_with_backend(capabilities)
            with stack:
                result = service.export(EditExportRequest(
                    str(source), str(output),
                    metadata_changes={"title": "Edited", "genre": "Test"},
                    lyrics_text="[00:01.00]Edited lyric",
                    cover_action="replace", cover_data=self._png_bytes(), cover_mime="image/png",
                ))
            self.assertTrue(result["success"], result)
            self.assertTrue(output.exists())
            self.assertEqual(source_hash, self._sha(source))
            self.assertTrue(result["verification_success"])
            self.assertIn(result["finalization_strategy"], {"hardlink", "exclusive_copy"})
            self.assertEqual("Edited", state["metadata"]["title"])
            self.assertEqual("Test", state["metadata"]["genre"])
            self.assertTrue(state["cover"])
            self.assertEqual("[00:01.00]Edited lyric", state["lyrics"])

            remove_output = root / "removed.flac"
            service, state, stack = self._service_with_backend((COVER_WRITE,))
            state["cover"] = True
            with stack:
                removed = service.export(EditExportRequest(str(source), str(remove_output), cover_action="remove"))
            self.assertTrue(removed["success"], removed)
            self.assertFalse(state["cover"])

    def test_lyrics_verification_accepts_reader_normalized_outer_newline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "edited.flac"
            service, state, stack = self._service_with_backend((LYRICS_WRITE,))
            requested = "[00:01.00]First line\n[00:02.00]Edited line\n"

            def normalized_lyrics_read(_path):
                return {
                    "ok": True,
                    "has_lyrics": True,
                    "lyrics_text": str(state["lyrics"]).strip(),
                }

            with stack, patch(
                "ui_next.bridge.edit_export_service.read_embedded_lyrics",
                side_effect=normalized_lyrics_read,
            ):
                result = service.export(
                    EditExportRequest(
                        str(source),
                        str(output),
                        lyrics_text=requested,
                    )
                )

            self.assertTrue(result["success"], result)
            self.assertTrue(result["verification_success"])
            self.assertEqual(requested, state["lyrics"])

    def test_missing_one_combined_capability_rejects_before_temp_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "edited.flac"
            request = EditExportRequest(str(source), str(output), metadata_changes={"title": "x"}, lyrics_text="x", cover_action="remove")
            with patch("ui_next.bridge.edit_export_service.shutil.copy2") as copy:
                result = EditExportService(CapabilityGate((METADATA_WRITE, LYRICS_WRITE))).export(request)
            self.assertEqual("capability_denied", result["error_code"])
            copy.assert_not_called()

    def test_pitch_and_metadata_are_rendered_into_one_verified_audio_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "combined.flac"
            service, state, stack = self._service_with_backend(
                (METADATA_WRITE, AUDIO_PROCESSING, AUDIO_EXPORT)
            )

            def render(_service, source_path, output_path, semitone):
                self.assertEqual(3, semitone)
                Path(output_path).write_bytes(
                    Path(source_path).read_bytes() + b"-pitch"
                )
                return {"success": True, "semitone": semitone}

            with stack, patch(
                "ui_next.bridge.edit_export_service.AudioProcessingService.render_pitch_shift",
                new=render,
            ), patch(
                "ui_next.bridge.edit_export_service.ProcessedAudioExportService._verify_preservation",
                return_value={"success": True},
            ):
                result = service.export(EditExportRequest(
                    str(source),
                    str(output),
                    metadata_changes={"title": "Combined"},
                    pitch_semitone=3,
                ))

            self.assertTrue(result["success"], result)
            self.assertEqual(["metadata", "pitch"], result["applied_operations"])
            self.assertEqual("Combined", state["metadata"]["title"])
            self.assertTrue(output.read_bytes().endswith(b"-pitch"))

    def test_each_write_or_verification_failure_cleans_temp_and_never_publishes(self):
        cases = (
            ("metadata", EditExportRequest, (METADATA_WRITE,), {"metadata_changes": {"title": "x"}}),
            ("cover", EditExportRequest, (COVER_WRITE,), {"cover_action": "remove"}),
            ("lyrics", EditExportRequest, (LYRICS_WRITE,), {"lyrics_text": "x"}),
        )
        for failing, request_type, capabilities, kwargs in cases:
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                source = self._source(root)
                source_hash = self._sha(source)
                output = root / f"{failing}.flac"
                service, _state, stack = self._service_with_backend(capabilities)
                target = {
                    "metadata": "write_audio_metadata",
                    "cover": "remove_audio_cover",
                    "lyrics": "embed_lrc_to_audio",
                }[failing]
                with stack, patch(f"ui_next.bridge.edit_export_service.{target}", return_value={"success": False, "error": "boom", "embedded": False}):
                    result = service.export(request_type(str(source), str(output), **kwargs))
                self.assertFalse(result["success"])
                self.assertIn("_write_failed", result["error_code"])
                self.assertFalse(output.exists())
                self.assertFalse(list(root.glob(".*.cherryq_edit_*.tmp.flac")))
                self.assertEqual(source_hash, self._sha(source))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "verify.flac"
            service, _state, stack = self._service_with_backend((METADATA_WRITE,))
            with stack, patch("ui_next.bridge.edit_export_service.read_audio_metadata", return_value={"ok": False}):
                result = service.export(EditExportRequest(str(source), str(output), metadata_changes={"title": "x"}))
            self.assertEqual("verification_failed", result["error_code"])
            self.assertFalse(output.exists())

    def test_post_publish_verification_failure_removes_only_owned_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "post-verify.flac"
            service, _state, stack = self._service_with_backend((METADATA_WRITE,))
            good = {"ok": True, "title": "x"}
            with stack, patch("ui_next.bridge.edit_export_service.read_audio_metadata", side_effect=[good, {"ok": False}]):
                result = service.export(EditExportRequest(str(source), str(output), metadata_changes={"title": "x"}))
            self.assertEqual("verification_failed", result["error_code"])
            self.assertFalse(output.exists())

    def test_exclusive_copy_fallback_and_conflict_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "fallback.flac"
            service, _state, stack = self._service_with_backend((METADATA_WRITE,))
            with stack, patch("ui_next.bridge.no_clobber_publish.os.link", side_effect=OSError("no hardlinks")):
                result = service.export(EditExportRequest(str(source), str(output), metadata_changes={"title": "x"}))
            self.assertTrue(result["success"], result)
            self.assertEqual("exclusive_copy", result["finalization_strategy"])

            conflict = root / "conflict.flac"
            service, _state, stack = self._service_with_backend((METADATA_WRITE,))
            with stack, patch("ui_next.bridge.no_clobber_publish.os.link", side_effect=FileExistsError):
                conflict_result = service.export(EditExportRequest(str(source), str(conflict), metadata_changes={"title": "x"}))
            self.assertEqual("output_conflict", conflict_result["error_code"])
            self.assertFalse(conflict.exists())

    def test_preview_and_legacy_live_cannot_bypass_write_capabilities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "blocked.flac"
            request = EditExportRequest(str(source), str(output), metadata_changes={"title": "x"})
            for gate in (CapabilityGate(), CapabilityGate((), legacy_live_requested=True)):
                self.assertEqual("capability_denied", EditExportService(gate).export(request)["error_code"])
            self.assertFalse(output.exists())

    def test_lrc_export_is_utf8_no_clobber_and_capability_gated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            original_lrc = root / "source.lrc"
            output = root / "edited.lrc"
            original_lrc.write_text("original", encoding="utf-8")
            original_hash = self._sha(original_lrc)
            request = LrcExportRequest(
                str(source), str(output), "[00:01.00]新的歌词", str(original_lrc)
            )
            denied = EditExportService(CapabilityGate()).export_lrc(request)
            self.assertEqual("capability_denied", denied["error_code"])
            self.assertFalse(output.exists())

            exported = EditExportService(CapabilityGate((LYRICS_WRITE,))).export_lrc(request)
            self.assertTrue(exported["success"], exported)
            self.assertEqual("UTF-8（无 BOM）", exported["encoding"])
            self.assertEqual("[00:01.00]新的歌词", output.read_text(encoding="utf-8"))
            self.assertEqual(original_hash, self._sha(original_lrc))
            self.assertEqual(
                "lrc_output_exists",
                EditExportService(CapabilityGate((LYRICS_WRITE,))).export_lrc(request)["error_code"],
            )

            same_path = LrcExportRequest(
                str(source),
                str(original_lrc),
                "[00:02.00]默认流程不可覆盖",
                str(original_lrc),
            )
            rejected = EditExportService(
                CapabilityGate((LYRICS_WRITE,))
            ).export_lrc(same_path)
            self.assertEqual("lrc_output_exists", rejected["error_code"])
            self.assertEqual(original_hash, self._sha(original_lrc))

            source_hash = self._sha(source)
            explicit_overwrite = LrcExportRequest(
                str(source),
                str(original_lrc),
                "[00:03.00]明确覆盖",
                str(original_lrc),
                overwrite_existing=True,
            )
            overwritten = EditExportService(
                CapabilityGate((LYRICS_WRITE,))
            ).export_lrc(explicit_overwrite)
            self.assertTrue(overwritten["success"], overwritten)
            self.assertTrue(overwritten["overwrote_original_lrc"])
            self.assertEqual(
                "explicit_atomic_lrc_replace",
                overwritten["finalization_strategy"],
            )
            self.assertEqual(
                "[00:03.00]明确覆盖",
                original_lrc.read_text(encoding="utf-8"),
            )
            self.assertEqual(source_hash, self._sha(source))

    def test_service_limits_replace_to_explicit_confirmed_overwrite_helpers(self):
        root = Path(__file__).resolve().parents[1]
        service_source = (root / "ui_next/bridge/edit_export_service.py").read_text(encoding="utf-8")
        publish_source = (root / "ui_next/bridge/no_clobber_publish.py").read_text(encoding="utf-8")
        no_clobber_body = publish_source.split("def publish_no_clobber", 1)[1].split(
            "def publish_confirmed_overwrite", 1
        )[0]
        self.assertNotIn("os.replace", no_clobber_body)
        self.assertIn("def publish_confirmed_overwrite", publish_source)
        self.assertIn("os.replace", publish_source)
        self.assertNotIn("import watcher", service_source)
        self.assertNotIn("save_config", service_source)
        self.assertNotIn("fileSession", service_source)

    def test_confirmed_existing_target_overwrite_is_verified_and_committed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            source_hash = self._sha(source)
            output = root / "existing.flac"
            output.write_bytes(b"old-output")
            service, state, stack = self._service_with_backend((METADATA_WRITE,))

            with stack:
                result = service.export(EditExportRequest(
                    str(source),
                    str(output),
                    metadata_changes={"title": "Confirmed"},
                    overwrite_existing=True,
                ))

            self.assertTrue(result["success"], result)
            self.assertTrue(result["overwrote_existing"])
            self.assertFalse(result["overwrote_source"])
            self.assertEqual("confirmed_atomic_replace", result["finalization_strategy"])
            self.assertEqual(b"original-audio-bytes", output.read_bytes())
            self.assertEqual(source_hash, self._sha(source))
            self.assertEqual("Confirmed", state["metadata"]["title"])
            self.assertEqual([], list(root.glob("*.cherryq_rollback_*.bak")))

    def test_confirmed_source_overwrite_reloads_from_a_verified_replacement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            original = source.read_bytes()
            service, state, stack = self._service_with_backend((METADATA_WRITE,))

            def write_and_change_bytes(path, values, overwrite=True):
                state["metadata"].update(values)
                Path(path).write_bytes(Path(path).read_bytes() + b"-edited")
                return {"success": True}

            with stack, patch(
                "ui_next.bridge.edit_export_service.write_audio_metadata",
                side_effect=write_and_change_bytes,
            ):
                result = service.export(EditExportRequest(
                    str(source),
                    str(source),
                    metadata_changes={"title": "Source edit"},
                    overwrite_existing=True,
                ))

            self.assertTrue(result["success"], result)
            self.assertTrue(result["overwrote_source"])
            self.assertFalse(result["sourceUnchanged"])
            self.assertNotEqual(original, source.read_bytes())
            self.assertEqual([], list(root.glob("*.cherryq_rollback_*.bak")))

    def test_post_overwrite_verification_failure_restores_original_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "existing.flac"
            original = b"must-be-restored"
            output.write_bytes(original)
            service, _state, stack = self._service_with_backend((METADATA_WRITE,))

            with stack, patch.object(
                service,
                "_verify",
                side_effect=[None, ("verification_failed", "post publish failed")],
            ):
                result = service.export(EditExportRequest(
                    str(source),
                    str(output),
                    metadata_changes={"title": "x"},
                    overwrite_existing=True,
                ))

            self.assertEqual("verification_failed", result["error_code"])
            self.assertEqual(original, output.read_bytes())
            self.assertEqual([], list(root.glob("*.cherryq_rollback_*.bak")))

    def test_confirmed_audio_overwrite_stops_if_target_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            output = root / "existing.flac"
            output.write_bytes(b"confirmed-target")
            service, _state, stack = self._service_with_backend((METADATA_WRITE,))

            def external_change(_temp, _request, _operations):
                output.write_bytes(b"external-change")
                return None

            with stack, patch.object(
                service,
                "_apply_operations",
                side_effect=external_change,
            ), patch.object(service, "_verify", return_value=None):
                result = service.export(EditExportRequest(
                    str(source),
                    str(output),
                    metadata_changes={"title": "x"},
                    overwrite_existing=True,
                ))

            self.assertEqual("overwrite_target_changed", result["error_code"])
            self.assertEqual(b"external-change", output.read_bytes())
            self.assertEqual([], list(root.glob("*.cherryq_rollback_*.bak")))

    def test_lrc_overwrite_stops_if_confirmed_target_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._source(root)
            original_lrc = root / "source.lrc"
            original_lrc.write_text("confirmed content", encoding="utf-8")
            request = LrcExportRequest(
                str(source),
                str(original_lrc),
                "new editor content",
                str(original_lrc),
                overwrite_existing=True,
            )

            def preview_with_external_change(path):
                preview_path = Path(path)
                text = preview_path.read_text(encoding="utf-8")
                if preview_path != original_lrc:
                    original_lrc.write_text(
                        "external change after confirmation",
                        encoding="utf-8",
                    )
                return {"ok": True, "lyrics_text": text}

            with patch(
                "ui_next.bridge.edit_export_service.read_lrc_file_preview",
                side_effect=preview_with_external_change,
            ):
                result = EditExportService(
                    CapabilityGate((LYRICS_WRITE,))
                ).export_lrc(request)

            self.assertEqual(
                "lrc_overwrite_target_changed",
                result["error_code"],
            )
            self.assertEqual(
                "external change after confirmation",
                original_lrc.read_text(encoding="utf-8"),
            )
            self.assertEqual([], list(root.glob("*.tmp.lrc")))


if __name__ == "__main__":
    unittest.main()

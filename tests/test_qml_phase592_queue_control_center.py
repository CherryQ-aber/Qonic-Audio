import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

import watcher
from ui_next.bridge.auto_convert_viewmodel import (
    AutoConvertViewModel,
    ConvertThread,
)
from ui_next.bridge.capabilities import (
    BATCH_CONVERT,
    QUEUE_MUTATION,
    CapabilityGate,
)
from ui_next.bridge.task_queue_model import TaskQueueModel


class Phase592QueueControlCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with watcher.pending_files_lock:
            watcher.pending_files.clear()
        with watcher.processed_files_lock:
            watcher.processed_files.clear()

    def tearDown(self):
        with watcher.pending_files_lock:
            watcher.pending_files.clear()
        with watcher.processed_files_lock:
            watcher.processed_files.clear()

    def _add_waiting(
        self,
        path: Path,
        output: Path,
        *,
        enabled: bool = True,
        target_override: str | None = None,
        output_override: str | None = None,
    ) -> None:
        path.write_bytes(path.name.encode("utf-8"))
        watcher.add_pending_file(
            str(path),
            status=watcher.WAITING_STATUS,
            task_snapshot={
                "target_format": "flac",
                "target_format_override": target_override,
                "output_directory": str(output),
                "output_directory_override": output_override,
                "enabled_for_run": enabled,
                "create_format_subfolder": False,
            },
        )

    def test_participation_is_independent_from_lifecycle_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "song.wav"
            source.write_bytes(b"audio")
            watcher.add_pending_file(str(source), status=watcher.WAITING_STATUS)

            self.assertTrue(
                watcher.set_pending_file_enabled_for_run(str(source), False)
            )
            task = watcher.get_task_snapshots()[0]
            self.assertFalse(task["enabled_for_run"])
            self.assertEqual(watcher.WAITING_STATUS, task["status"])
            self.assertEqual([], watcher.get_convertible_tasks())

            self.assertTrue(
                watcher.set_pending_file_enabled_for_run(str(source), True)
            )
            self.assertTrue(watcher.get_task_snapshots()[0]["enabled_for_run"])
            self.assertEqual(1, len(watcher.get_convertible_tasks()))

            watcher.set_pending_file_status(str(source), watcher.PROCESSING_STATUS)
            self.assertFalse(
                watcher.set_pending_file_enabled_for_run(str(source), False)
            )

    def test_target_and_output_overrides_are_task_local_and_retry_keeps_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "中文 song.wav"
            source.write_bytes(b"audio")
            override = root / "跨盘 模拟" / ("长目录" * 12)
            override.mkdir(parents=True)
            watcher.add_pending_file(
                str(source),
                status=watcher.FAILED_STATUS,
                task_snapshot={
                    "target_format": "flac",
                    "target_format_override": None,
                    "output_directory": str(root),
                    "output_directory_override": None,
                },
            )

            self.assertTrue(
                watcher.set_pending_file_target_format(str(source), "mp3")
            )
            self.assertTrue(
                watcher.set_pending_file_output_directory_override(
                    str(source),
                    str(override),
                )
            )
            summary = watcher.retry_failed_files([str(source)])
            task = watcher.get_task_snapshots()[0]

            self.assertEqual(1, summary["requeued_count"])
            self.assertEqual("mp3", task["target_format_override"])
            self.assertEqual(
                os.path.normpath(os.path.abspath(override)),
                task["output_directory_override"],
            )
            self.assertEqual(watcher.QUEUED_STATUS, task["status"])

    def test_batch_dispatch_filters_disabled_and_resolves_task_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            default_output = root / "default output"
            custom_output = root / "custom output"
            default_output.mkdir()
            custom_output.mkdir()
            first = root / "first.wav"
            skipped = root / "skipped.wav"
            custom = root / "custom.wav"
            self._add_waiting(first, default_output)
            self._add_waiting(skipped, default_output, enabled=False)
            self._add_waiting(
                custom,
                default_output,
                target_override="mp3",
                output_override=str(custom_output),
            )

            thread = ConvertThread(
                "flac",
                output_root_override=str(default_output),
                create_format_subfolder=False,
            )
            outputs = iter(
                [
                    str(default_output / "first.flac"),
                    str(custom_output / "custom.mp3"),
                ]
            )
            with patch(
                "converter.convert_audio",
                side_effect=lambda *args, **kwargs: {
                    "success": True,
                    "output_path": next(outputs),
                },
            ) as convert:
                thread.run()

            self.assertEqual(2, convert.call_count)
            self.assertEqual("flac", convert.call_args_list[0].args[1])
            self.assertEqual(
                str(default_output),
                convert.call_args_list[0].kwargs["output_root_override"],
            )
            self.assertEqual("mp3", convert.call_args_list[1].args[1])
            self.assertEqual(
                str(custom_output),
                convert.call_args_list[1].kwargs["output_root_override"],
            )
            self.assertEqual(
                watcher.WAITING_STATUS,
                watcher.get_pending_file_status(str(skipped)),
            )
            self.assertFalse(
                next(
                    task
                    for task in watcher.get_task_snapshots()
                    if task["path"] == str(skipped)
                )["enabled_for_run"]
            )

    def test_explicit_single_dispatch_can_run_disabled_task_only_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "output"
            output.mkdir()
            first = root / "first.wav"
            other = root / "other.wav"
            self._add_waiting(first, output, enabled=False)
            self._add_waiting(other, output)

            thread = ConvertThread(
                "flac",
                output_root_override=str(output),
                selected_paths={str(first)},
                include_disabled=True,
            )
            with patch(
                "converter.convert_audio",
                return_value={
                    "success": True,
                    "output_path": str(output / "first.flac"),
                },
            ) as convert:
                thread.run()

            self.assertEqual(1, convert.call_count)
            self.assertEqual(
                watcher.COMPLETED_STATUS,
                watcher.get_pending_file_status(str(first)),
            )
            self.assertEqual(
                watcher.WAITING_STATUS,
                watcher.get_pending_file_status(str(other)),
            )

    def test_viewmodel_bulk_policy_does_not_save_global_config(self):
        gate = CapabilityGate((QUEUE_MUTATION, BATCH_CONVERT))
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "临时 输出"
            output.mkdir()
            first = root / "one.wav"
            second = root / "two.wav"
            self._add_waiting(first, output)
            self._add_waiting(second, output)
            view_model = AutoConvertViewModel(
                queue_model,
                capability_gate=gate,
            )
            with patch(
                "ui_next.bridge.auto_convert_viewmodel.save_config",
                side_effect=AssertionError("task policy must not save config"),
            ):
                view_model.set_tasks_enabled_for_run(
                    [str(first), str(second)],
                    False,
                )
                view_model.set_tasks_target_format(
                    [str(first), str(second)],
                    "opus",
                )
                view_model._set_tasks_output_directory(
                    [str(first), str(second)],
                    str(output),
                )

            tasks = watcher.get_task_snapshots()
            self.assertTrue(all(not task["enabled_for_run"] for task in tasks))
            self.assertTrue(
                all(task["target_format_override"] == "opus" for task in tasks)
            )
            self.assertTrue(
                all(task["output_directory_override"] == str(output) for task in tasks)
            )
            view_model.shutdown()

    def test_preview_mode_cannot_mutate_task_policy_or_dispatch(self):
        queue_model = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "song.wav"
            output = root / "output"
            output.mkdir()
            self._add_waiting(source, output)
            before = watcher.get_task_snapshots()[0]
            view_model = AutoConvertViewModel(
                queue_model,
                capability_gate=CapabilityGate(),
            )

            view_model.set_tasks_enabled_for_run([str(source)], False)
            view_model.set_tasks_target_format([str(source)], "mp3")
            view_model.reset_tasks_output_directory([str(source)])
            view_model.start_convert_selected([str(source)])

            after = watcher.get_task_snapshots()[0]
            self.assertEqual(before["enabled_for_run"], after["enabled_for_run"])
            self.assertEqual(
                before["target_format_override"],
                after["target_format_override"],
            )
            self.assertEqual(
                before["output_directory_override"],
                after["output_directory_override"],
            )
            self.assertIsNone(view_model._convert_thread)
            view_model.shutdown()

    def test_model_roles_and_qml_use_stable_paths_for_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "song.wav"
            output = root / "output"
            output.mkdir()
            self._add_waiting(
                source,
                output,
                enabled=False,
                target_override="mp3",
                output_override=str(output),
            )
            model = TaskQueueModel(
                capability_gate=CapabilityGate((QUEUE_MUTATION,))
            )
            index = model.index(0, 0, QModelIndex())
            self.assertFalse(model.data(index, model.enabledForRunRole))
            self.assertEqual(
                "本轮跳过",
                model.data(index, model.participationLabelRole),
            )
            self.assertEqual(
                "指定目录",
                model.data(index, model.outputStrategyLabelRole),
            )
            self.assertEqual(str(source), model.pathAt(0))
            self.assertTrue(model.containsPath(str(source)))

            project_root = Path(__file__).resolve().parents[1]
            queue_qml = (
                project_root / "ui_next/qml/components/TaskQueueView.qml"
            ).read_text(encoding="utf-8")
            row_qml = (
                project_root / "ui_next/qml/components/TaskRowDelegate.qml"
            ).read_text(encoding="utf-8")
            self.assertIn("selectedPaths", queue_qml)
            self.assertIn("queueModel.pathAt(row)", queue_qml)
            self.assertIn("queueModel.containsPath(path)", queue_qml)
            self.assertNotIn("pending_files", queue_qml)
            self.assertIn('text: "转换选中文件"', row_qml)
            self.assertIn('text: "打开源文件位置"', row_qml)
            self.assertIn("model: root.formatOptions", row_qml)
            self.assertIn("effectiveTargetFormat: model.effectiveTargetFormat", queue_qml)
            self.assertIn("sameFormatWarning: model.sameFormatWarning", queue_qml)
            self.assertIn("plannedOutputPath: model.plannedOutputPath", queue_qml)
            self.assertIn("outputNameConflict: model.outputNameConflict", queue_qml)
            self.assertIn("queueWarningText: model.queueWarningText", queue_qml)
            self.assertIn("root.sameFormatWarning", row_qml)
            self.assertIn("root.outputNameConflict", row_qml)
            self.assertIn("stageTakesDetailPriority", row_qml)
            self.assertIn(
                "(stageTakesDetailPriority ? stage : queueWarningText)",
                row_qml,
            )
            self.assertIn("text: root.primaryDetailText", row_qml)
            self.assertNotIn("ComboBox {", row_qml)

    def test_queue_warnings_are_derived_without_changing_task_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "song.flac"
            source.write_bytes(b"audio")
            watcher.add_pending_file(
                str(source),
                status=watcher.WAITING_STATUS,
                task_snapshot={
                    "target_format": "flac",
                    "target_format_override": None,
                    "output_directory": str(root),
                    "output_directory_override": None,
                    "enabled_for_run": True,
                    "create_format_subfolder": False,
                },
            )

            with (
                patch(
                    "ui_next.bridge.task_queue_model.get_target_format",
                    return_value="flac",
                ),
                patch(
                    "ui_next.bridge.task_queue_model.get_output_folder",
                    return_value=str(root),
                ),
                patch(
                    "ui_next.bridge.task_queue_model.get_create_format_subfolder",
                    return_value=True,
                ),
            ):
                model = TaskQueueModel(
                    capability_gate=CapabilityGate((QUEUE_MUTATION,))
                )
                index = model.index(0, 0, QModelIndex())
                role_names = set(model.roleNames().values())

                self.assertIn(b"effectiveTargetFormat", role_names)
                self.assertIn(b"sameFormatWarning", role_names)
                self.assertIn(b"plannedOutputPath", role_names)
                self.assertIn(b"outputNameConflict", role_names)
                self.assertIn(b"queueWarningText", role_names)
                self.assertEqual(
                    "flac",
                    model.data(index, model.effectiveTargetFormatRole),
                )
                self.assertTrue(model.data(index, model.sameFormatWarningRole))
                self.assertEqual(
                    str(source),
                    model.data(index, model.plannedOutputPathRole),
                )
                self.assertTrue(model.data(index, model.outputNameConflictRole))
                warning = model.data(index, model.queueWarningTextRole)
                self.assertTrue(
                    warning.startswith("根目录下已有相同文件")
                )
                self.assertIn("根目录下已有相同文件", warning)
                self.assertTrue(model.data(index, model.canConvertRole))
                self.assertTrue(model.data(index, model.enabledForRunRole))
                self.assertTrue(
                    model.data(index, model.canChangeTargetFormatRole)
                )

                self.assertTrue(
                    watcher.set_pending_file_target_format(str(source), "mp3")
                )
                model.manualRefresh()
                index = model.index(0, 0, QModelIndex())

                self.assertEqual(
                    "mp3",
                    model.data(index, model.effectiveTargetFormatRole),
                )
                self.assertFalse(model.data(index, model.sameFormatWarningRole))
                self.assertEqual(
                    str(root / "song.mp3"),
                    model.data(index, model.plannedOutputPathRole),
                )
                self.assertFalse(model.data(index, model.outputNameConflictRole))
                self.assertEqual("", model.data(index, model.queueWarningTextRole))
                self.assertEqual(
                    watcher.WAITING_STATUS,
                    model.data(index, model.statusRole),
                )
                self.assertTrue(model.data(index, model.canConvertRole))
                self.assertTrue(model.data(index, model.enabledForRunRole))
                self.assertTrue(
                    model.data(index, model.canChangeTargetFormatRole)
                )

    def test_same_format_stage_warning_uses_requested_plain_label(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "song.flac"
            output = root / "empty-output"
            source.parent.mkdir()
            source.write_bytes(b"audio")
            watcher.add_pending_file(
                str(source),
                status=watcher.WAITING_STATUS,
                task_snapshot={
                    "target_format_override": "flac",
                    "output_directory_override": str(output),
                    "enabled_for_run": True,
                    "create_format_subfolder": False,
                },
            )

            model = TaskQueueModel(
                capability_gate=CapabilityGate((QUEUE_MUTATION,))
            )
            index = model.index(0, 0, QModelIndex())

            self.assertTrue(model.data(index, model.sameFormatWarningRole))
            self.assertFalse(model.data(index, model.outputNameConflictRole))
            self.assertEqual(
                "根目录下已有相同文件",
                model.data(index, model.queueWarningTextRole),
            )
            self.assertTrue(model.data(index, model.canConvertRole))
            self.assertTrue(
                model.data(index, model.canChangeTargetFormatRole)
            )

    def test_planned_output_path_preserves_relative_and_format_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "album" / "song.wav"
            source.parent.mkdir(parents=True)
            output = root / "output"
            source.write_bytes(b"audio")
            watcher.add_pending_file(
                str(source),
                status=watcher.WAITING_STATUS,
                task_snapshot={
                    "target_format": "flac",
                    "target_format_override": "mp3",
                    "output_directory": str(root / "snapshot"),
                    "output_directory_override": str(output),
                    "relative_output_path": str(Path("album") / source.name),
                    "preserve_relative_structure": True,
                    "create_format_subfolder": True,
                },
            )

            with patch(
                "ui_next.bridge.task_queue_model.get_target_format",
                return_value="flac",
            ):
                model = TaskQueueModel()
                index = model.index(0, 0, QModelIndex())

            self.assertEqual(
                str(output / "album" / "MP3" / "song.mp3"),
                model.data(index, model.plannedOutputPathRole),
            )
            self.assertFalse(output.exists())
            self.assertFalse(model.data(index, model.sameFormatWarningRole))
            self.assertFalse(model.data(index, model.outputNameConflictRole))

    def test_global_output_change_refreshes_planned_conflict_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "song.wav"
            source.parent.mkdir()
            source.write_bytes(b"audio")
            first_output = root / "first"
            second_output = root / "second"
            second_output.mkdir()
            (second_output / "song.mp3").write_bytes(b"existing")
            watcher.add_pending_file(
                str(source),
                status=watcher.WAITING_STATUS,
                task_snapshot={
                    "target_format": "flac",
                    "target_format_override": "mp3",
                    "output_directory": str(root / "stale snapshot"),
                    "output_directory_override": None,
                    "create_format_subfolder": False,
                },
            )
            current_output = {"path": str(first_output)}

            with (
                patch(
                    "ui_next.bridge.task_queue_model.get_target_format",
                    return_value="flac",
                ),
                patch(
                    "ui_next.bridge.task_queue_model.get_output_folder",
                    side_effect=lambda: current_output["path"],
                ),
                patch(
                    "ui_next.bridge.task_queue_model.get_create_format_subfolder",
                    return_value=False,
                ),
            ):
                model = TaskQueueModel()
                index = model.index(0, 0, QModelIndex())
                self.assertEqual(
                    str(first_output / "song.mp3"),
                    model.data(index, model.plannedOutputPathRole),
                )
                self.assertFalse(model.data(index, model.outputNameConflictRole))

                current_output["path"] = str(second_output)
                model.manualRefresh()
                index = model.index(0, 0, QModelIndex())

            self.assertEqual(
                str(second_output / "song.mp3"),
                model.data(index, model.plannedOutputPathRole),
            )
            self.assertTrue(model.data(index, model.outputNameConflictRole))
            self.assertIn(
                "根目录下已有相同文件",
                model.data(index, model.queueWarningTextRole),
            )
            self.assertEqual(
                watcher.WAITING_STATUS,
                model.data(index, model.statusRole),
            )

    def test_completed_own_output_is_not_reported_as_name_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.flac"
            output = root / "output"
            output.mkdir()
            source.write_bytes(b"audio")
            planned_output = output / "source.flac"
            planned_output.write_bytes(b"converted")
            watcher.add_pending_file(
                str(source),
                status=watcher.COMPLETED_STATUS,
                task_snapshot={
                    "target_format": "flac",
                    "target_format_override": "flac",
                    "output_directory_override": str(output),
                    "create_format_subfolder": False,
                },
            )
            self.assertTrue(
                watcher.set_pending_file_runtime_data(
                    str(source),
                    output_path=str(planned_output),
                    stage="转换完成，正式输出已发布",
                )
            )

            model = TaskQueueModel()
            index = model.index(0, 0, QModelIndex())

            self.assertEqual(
                str(planned_output),
                model.data(index, model.plannedOutputPathRole),
            )
            self.assertFalse(model.data(index, model.outputNameConflictRole))
            self.assertFalse(model.data(index, model.sameFormatWarningRole))
            self.assertEqual("", model.data(index, model.queueWarningTextRole))
            self.assertEqual(
                "转换完成，正式输出已发布",
                model.data(index, model.stageRole),
            )
            self.assertFalse(
                model.data(index, model.canChangeTargetFormatRole)
            )

    def test_queue_tasks_with_same_planned_output_are_warned_without_state_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "output"
            first = root / "one" / "same.wav"
            second = root / "two" / "same.wav"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            for source in (first, second):
                watcher.add_pending_file(
                    str(source),
                    status=watcher.WAITING_STATUS,
                    task_snapshot={
                        "target_format_override": "mp3",
                        "output_directory_override": str(output),
                        "enabled_for_run": True,
                        "create_format_subfolder": False,
                    },
                )

            model = TaskQueueModel(
                capability_gate=CapabilityGate((QUEUE_MUTATION,))
            )
            expected_path = str(output / "same.mp3")
            self.assertFalse(output.exists())
            for row in range(model.rowCount()):
                index = model.index(row, 0, QModelIndex())
                self.assertEqual(
                    expected_path,
                    model.data(index, model.plannedOutputPathRole),
                )
                self.assertTrue(
                    model.data(index, model.outputNameConflictRole)
                )
                self.assertIn(
                    "多个任务计划输出到同一路径",
                    model.data(index, model.queueWarningTextRole),
                )
                self.assertEqual(
                    watcher.WAITING_STATUS,
                    model.data(index, model.statusRole),
                )
                self.assertTrue(model.data(index, model.enabledForRunRole))
                self.assertTrue(model.data(index, model.canConvertRole))
                self.assertTrue(
                    model.data(index, model.canChangeTargetFormatRole)
                )

            self.assertTrue(
                watcher.set_pending_file_status(
                    str(first),
                    watcher.PROCESSING_STATUS,
                )
            )
            model.manualRefresh()
            processing_index = model.index(0, 0, QModelIndex())
            waiting_index = model.index(1, 0, QModelIndex())
            self.assertFalse(
                model.data(processing_index, model.outputNameConflictRole)
            )
            self.assertEqual(
                "",
                model.data(processing_index, model.queueWarningTextRole),
            )
            self.assertTrue(
                model.data(waiting_index, model.outputNameConflictRole)
            )
            self.assertIn(
                "多个任务计划输出到同一路径",
                model.data(waiting_index, model.queueWarningTextRole),
            )


if __name__ == "__main__":
    unittest.main()

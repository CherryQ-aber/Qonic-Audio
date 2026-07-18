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


if __name__ == "__main__":
    unittest.main()

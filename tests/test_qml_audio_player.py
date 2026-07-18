import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer

from ui_next.bridge.audio_player_viewmodel import AudioPlayerViewModel
from ui_next.bridge.capabilities import (
    AUDIO_PLAYBACK,
    DEFAULT_USER_MODE,
    PREVIEW_MODE,
    TEST_MODE,
    CapabilityGate,
)
from ui_next.bridge.file_session_viewmodel import FileSessionViewModel


class _FakeAudioOutput(QObject):
    def __init__(self, device=None):
        super().__init__()
        self.volume = 0.0
        self.volume_history = []
        self.muted = False
        self._device = device
        self.device_history = []

    def setVolume(self, value):
        self.volume = value
        self.volume_history.append(value)

    def setDevice(self, device):
        self._device = device
        self.muted = False
        self.device_history.append(device)

    def device(self):
        return self._device

    def setMuted(self, value):
        self.muted = bool(value)

    def isMuted(self):
        return self.muted


class _FakePlayer(QObject):
    playbackStateChanged = Signal(object)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    mediaStatusChanged = Signal(object)
    errorOccurred = Signal(object, str)

    def __init__(self):
        super().__init__()
        self.source = QUrl()
        self.output = None
        self.position = 0
        self.stop_count = 0
        self.set_source_count = 0

    def setAudioOutput(self, output):
        self.output = output

    def setSource(self, source):
        self.source = source
        self.position = 0
        self.set_source_count += 1

    def play(self):
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)

    def pause(self):
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PausedState)

    def stop(self):
        self.stop_count += 1
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)

    def setPosition(self, position):
        self.position = position
        self.positionChanged.emit(position)

    def errorString(self):
        return "unsupported codec"


class _FakeAudioDevice:
    def __init__(self, device_id, name):
        self._device_id = str(device_id).encode("utf-8")
        self._name = str(name)

    def id(self):
        return self._device_id

    def description(self):
        return self._name


class _FakeMediaDevices:
    outputs = []
    default_output = None

    @classmethod
    def audioOutputs(cls):
        return list(cls.outputs)

    @classmethod
    def defaultAudioOutput(cls):
        return cls.default_output


class AudioPlayerViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _build_player(
        self,
        enabled=True,
        *,
        runtime_mode=DEFAULT_USER_MODE,
        fake_player=None,
        fake_output=None,
    ):
        gate = CapabilityGate(
            (AUDIO_PLAYBACK,) if enabled else (),
            runtime_mode=runtime_mode,
        )
        session = FileSessionViewModel(gate)
        fake_player = fake_player or _FakePlayer()
        fake_output = fake_output or _FakeAudioOutput()
        view_model = AudioPlayerViewModel(
            session,
            gate,
            media_player=fake_player,
            audio_output=fake_output,
        )
        return session, view_model, fake_player, fake_output

    def test_disabled_playback_capability_keeps_player_empty(self):
        session, player, fake, _output = self._build_player(enabled=False)
        self.assertEqual("empty", player.playerState)
        self.assertFalse(player.canPlay)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "preview.wav"
            path.write_bytes(b"audio")
            session.setCurrentFile(str(path), "audio_editor")
        self.assertEqual("empty", player.playerState)
        self.assertTrue(fake.source.isEmpty())

    def test_preview_and_test_modes_do_not_construct_real_multimedia_backends(self):
        for runtime_mode in (PREVIEW_MODE, TEST_MODE):
            with self.subTest(runtime_mode=runtime_mode):
                gate = CapabilityGate(
                    (AUDIO_PLAYBACK,),
                    runtime_mode=runtime_mode,
                )
                session = FileSessionViewModel(gate)
                with (
                    patch(
                        "ui_next.bridge.audio_player_viewmodel.QMediaPlayer",
                        side_effect=AssertionError(
                            "preview/test must not create QMediaPlayer"
                        ),
                    ) as player_constructor,
                    patch(
                        "ui_next.bridge.audio_player_viewmodel.QAudioOutput",
                        side_effect=AssertionError(
                            "preview/test must not create QAudioOutput"
                        ),
                    ) as output_constructor,
                ):
                    player = AudioPlayerViewModel(session, gate)

                self.assertFalse(player.backendInitialized)
                self.assertFalse(player.canPlay)
                self.assertEqual("_NullMediaPlayer", type(player._player).__name__)
                self.assertEqual("_NullAudioOutput", type(player._audio_output).__name__)
                player_constructor.assert_not_called()
                output_constructor.assert_not_called()
                player.shutdown()
                session.shutdown()

    def test_default_user_mode_constructs_exactly_one_player_and_audio_output(self):
        fake_player = _FakePlayer()
        fake_output = _FakeAudioOutput()
        gate = CapabilityGate(
            (AUDIO_PLAYBACK,),
            runtime_mode=DEFAULT_USER_MODE,
        )
        session = FileSessionViewModel(gate)

        with (
            patch(
                "ui_next.bridge.audio_player_viewmodel.QMediaPlayer",
                return_value=fake_player,
            ) as player_constructor,
            patch(
                "ui_next.bridge.audio_player_viewmodel.QAudioOutput",
                return_value=fake_output,
            ) as output_constructor,
        ):
            player = AudioPlayerViewModel(session, gate)

        self.assertTrue(player.backendInitialized)
        self.assertIs(fake_player, player._player)
        self.assertIs(fake_output, player._audio_output)
        self.assertIs(fake_output, fake_player.output)
        player_constructor.assert_called_once_with(player)
        output_constructor.assert_called_once_with(player)
        player.shutdown()
        session.shutdown()

    def test_load_play_pause_stop_seek_volume_and_clear_follow_session(self):
        session, player, fake, output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.wav"
            second = Path(temp_dir) / "second.wav"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            session.setCurrentFile(str(first), "audio_editor")
            self.assertEqual("loading", player.playerState)
            self.assertEqual(first.resolve(), Path(fake.source.toLocalFile()).resolve())
            fake.durationChanged.emit(120000)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
            self.assertEqual("ready", player.playerState)
            self.assertTrue(player.canPlay)

            player.play()
            self.assertEqual("playing", player.playerState)
            player.pause()
            self.assertEqual("paused", player.playerState)
            player.seek(45000)
            self.assertEqual(45000, player.position)
            player.setVolume(37.6)
            self.assertEqual(38, player.volume)
            self.assertAlmostEqual(0.38, output.volume)
            player.stop()
            self.assertEqual("stopped", player.playerState)
            self.assertEqual(0, player.position)

            session.setCurrentFile(str(second), "metadata_page")
            self.assertEqual(second.resolve(), Path(fake.source.toLocalFile()).resolve())
            self.assertGreaterEqual(fake.stop_count, 2)
            session.clearCurrentFile()
            self.assertEqual("empty", player.playerState)
            self.assertTrue(fake.source.isEmpty())

    def test_playback_source_types_keep_file_session_as_original_authority(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            original = Path(temp_dir) / "original.wav"
            preview = Path(temp_dir) / "preview.wav"
            exported = Path(temp_dir) / "exported.wav"
            for path in (original, preview, exported):
                path.write_bytes(path.stem.encode("utf-8"))

            session.setCurrentFile(str(original), "audio_editor")
            self.assertEqual("original", player.currentPlaybackSourceType)
            self.assertEqual(
                original.resolve(),
                Path(player.currentPlaybackSourcePath).resolve(),
            )

            player.setPlaybackSource(str(preview), "Pitch 试听", False, 0)
            self.assertEqual("preview_cache", player.currentPlaybackSourceType)
            self.assertEqual(
                original.resolve(),
                Path(session.currentFilePath).resolve(),
            )

            player.setPlaybackSourceWithType(
                str(exported),
                "导出结果",
                "export_result",
                False,
                0,
            )
            self.assertEqual("export_result", player.currentPlaybackSourceType)
            self.assertEqual(
                original.resolve(),
                Path(session.currentFilePath).resolve(),
            )

            fake.position = 7300
            player.returnToOriginal()
            self.assertEqual("original", player.currentPlaybackSourceType)
            self.assertEqual(0, fake.position)
            self.assertEqual(
                original.resolve(),
                Path(fake.source.toLocalFile()).resolve(),
            )

    def test_release_and_restore_preserve_session_source_type_and_position(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            original = Path(temp_dir) / "release.wav"
            original.write_bytes(b"audio")
            session.setCurrentFile(str(original), "audio_editor")
            fake.durationChanged.emit(60000)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
            player.seek(12345)
            self.assertEqual(12345, player.position)

            self.assertTrue(player.releaseMediaSource())
            self.assertTrue(player.mediaSourceReleased)
            self.assertTrue(fake.source.isEmpty())
            self.assertEqual(
                original.resolve(),
                Path(session.currentFilePath).resolve(),
            )

            self.assertTrue(player.restorePlaybackSource())
            self.assertEqual("loading", player.playerState)
            self.assertEqual("original", player.currentPlaybackSourceType)
            self.assertEqual(12345, fake.position)
            self.assertEqual(
                original.resolve(),
                Path(fake.source.toLocalFile()).resolve(),
            )

    def test_refresh_devices_does_not_switch_until_explicit_selection(self):
        first = _FakeAudioDevice("device-a", "设备 A")
        second = _FakeAudioDevice("device-b", "设备 B")
        output = _FakeAudioOutput(first)
        session, player, _fake, output = self._build_player(fake_output=output)
        _FakeMediaDevices.outputs = [first, second]
        _FakeMediaDevices.default_output = second

        with patch(
            "ui_next.bridge.audio_player_viewmodel.QMediaDevices",
            _FakeMediaDevices,
        ):
            player.refreshOutputDevices()
            first_id = player.outputDevices[0]["id"]
            second_id = player.outputDevices[1]["id"]
            self.assertEqual(first_id, player.selectedOutputDeviceId)
            self.assertEqual([], output.device_history)

            player.refreshOutputDevices()
            self.assertEqual([], output.device_history)
            self.assertTrue(player.selectOutputDevice(second_id))

        self.assertIs(second, output.device())
        self.assertEqual([second], output.device_history)
        self.assertEqual(second_id, player.selectedOutputDeviceId)
        self.assertEqual("设备 B", player.outputDeviceName)
        self.assertAlmostEqual(0.7, output.volume)

    def test_same_name_devices_keep_distinct_stable_ids(self):
        first = _FakeAudioDevice("same-name-a", "USB Audio")
        second = _FakeAudioDevice("same-name-b", "USB Audio")
        output = _FakeAudioOutput(first)
        _session, player, _fake, output = self._build_player(
            fake_output=output
        )
        _FakeMediaDevices.outputs = [first, second]
        _FakeMediaDevices.default_output = first

        with patch(
            "ui_next.bridge.audio_player_viewmodel.QMediaDevices",
            _FakeMediaDevices,
        ):
            player.refreshOutputDevices()
            self.assertEqual(
                ["USB Audio", "USB Audio"],
                [item["name"] for item in player.outputDevices],
            )
            first_id, second_id = [
                item["id"] for item in player.outputDevices
            ]
            self.assertNotEqual(first_id, second_id)
            self.assertTrue(player.selectOutputDevice(second_id))

        self.assertIs(second, output.device())
        self.assertEqual(second_id, player.selectedOutputDeviceId)

    def test_disappearing_selected_device_keeps_volume_and_muted_state(self):
        first = _FakeAudioDevice("device-a", "设备 A")
        second = _FakeAudioDevice("device-b", "设备 B")
        output = _FakeAudioOutput(second)
        session, player, _fake, output = self._build_player(fake_output=output)
        player.setVolume(42)
        player.setMuted(True)
        _FakeMediaDevices.outputs = [first, second]
        _FakeMediaDevices.default_output = first

        with patch(
            "ui_next.bridge.audio_player_viewmodel.QMediaDevices",
            _FakeMediaDevices,
        ):
            player.refreshOutputDevices()
            second_id = player.outputDevices[1]["id"]
            self.assertEqual(second_id, player.selectedOutputDeviceId)

            _FakeMediaDevices.outputs = [first]
            _FakeMediaDevices.default_output = first
            player.refreshOutputDevices()

        self.assertIs(first, output.device())
        self.assertEqual(player.outputDevices[0]["id"], player.selectedOutputDeviceId)
        self.assertEqual("设备 A", player.outputDeviceName)
        self.assertEqual(42, player.volume)
        self.assertAlmostEqual(0.42, output.volume)
        self.assertTrue(player.muted)
        self.assertTrue(output.muted)
        self.assertIn("回退", player.statusMessage)

    def test_missing_current_file_marks_file_session_and_releases_source(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "missing.wav"
            source.write_bytes(b"audio")
            session.setCurrentFile(str(source), "audio_editor")
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
            source.unlink()

            player.play()

            self.assertEqual("error", player.playerState)
            self.assertEqual("none", player.currentPlaybackSourceType)
            self.assertEqual("", player.currentPlaybackSourcePath)
            self.assertTrue(fake.source.isEmpty())
            self.assertEqual("missing", session.sessionState)
            self.assertIn("不存在", player.error)

    def test_late_signals_from_old_source_cannot_pollute_new_source(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.wav"
            second = Path(temp_dir) / "second.wav"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            session.setCurrentFile(str(first), "audio_editor")
            old_handlers = [handler for _signal, handler in player._signal_bindings]
            fake.durationChanged.emit(1111)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)

            session.setCurrentFile(str(second), "audio_editor")
            fake.durationChanged.emit(2222)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
            self.assertEqual("ready", player.playerState)
            self.assertEqual(2222, player.duration)

            old_handlers[2](999999)
            old_handlers[3](QMediaPlayer.MediaStatus.EndOfMedia)
            old_handlers[4](0, "unsupported codec")

            self.assertEqual("ready", player.playerState)
            self.assertEqual(2222, player.duration)
            self.assertEqual("", player.error)
            self.assertEqual(
                second.resolve(),
                Path(player.currentPlaybackSourcePath).resolve(),
            )

    def test_end_of_media_enters_finished_and_replay_starts_from_zero(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "finished.wav"
            source.write_bytes(b"audio")
            session.setCurrentFile(str(source), "audio_editor")
            fake.durationChanged.emit(9000)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)

            self.assertEqual("finished", player.playerState)
            self.assertEqual(9000, player.position)
            self.assertTrue(player.canPlay)

            fake.position = 9000
            player.play()
            self.assertEqual(0, fake.position)
            self.assertEqual("playing", player.playerState)

    def test_volume_and_seek_boundaries_survive_file_switch_without_rebuild(self):
        session, player, fake, output = self._build_player()
        original_player = player._player
        original_output = player._audio_output
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.wav"
            second = Path(temp_dir) / "second.wav"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            session.setCurrentFile(str(first), "audio_editor")
            fake.durationChanged.emit(10_000)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)

            player.setVolume(-10)
            self.assertEqual(0, player.volume)
            player.setVolume(63)
            self.assertEqual(63, player.volume)
            self.assertAlmostEqual(0.63, output.volume)
            player.seek(99_999)
            self.assertEqual(10_000, player.position)
            player.seek(-100)
            self.assertEqual(0, player.position)

            session.setCurrentFile(str(second), "audio_editor")
            self.assertEqual(63, player.volume)
            self.assertIs(original_player, player._player)
            self.assertIs(original_output, player._audio_output)
            self.assertEqual(0, player.position)

            # Unknown duration safely ignores seek requests.
            player.seek(5_000)
            self.assertEqual(0, player.position)
            player.setVolume(150)
            self.assertEqual(100, player.volume)

    def test_copy_current_timestamp_uses_real_player_position(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "timestamp.wav"
            source.write_bytes(b"audio")
            session.setCurrentFile(str(source), "audio_editor")
            fake.durationChanged.emit(600_000)
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
            fake.positionChanged.emit(201_450)

            with patch(
                "ui_next.bridge.audio_player_viewmodel.QGuiApplication"
            ) as gui_application:
                copied = player.copyCurrentTimestamp()

        self.assertEqual("[03:21.450]", copied)
        gui_application.clipboard.return_value.setText.assert_called_once_with(
            "[03:21.450]"
        )
        self.assertIn("[03:21.450]", player.statusMessage)

        fake.positionChanged.emit(15)
        self.assertEqual(
            "[00:00.015]",
            player.currentTimestampText,
            "默认时间点精度必须为千分之一秒",
        )
        player.setTimestampPrecision("centisecond")
        self.assertEqual("centisecond", player.timestampPrecision)
        self.assertEqual("[00:00.02]", player.currentTimestampText)
        player.setTimestampPrecision("invalid")
        self.assertEqual("millisecond", player.timestampPrecision)
        self.assertEqual("[00:00.015]", player.currentTimestampText)

    def test_player_error_is_specific(self):
        _session, player, fake, _output = self._build_player()
        fake.errorOccurred.emit(0, "unsupported codec")
        self.assertEqual("error", player.playerState)
        self.assertIn("不支持", player.error)
        self.assertTrue(fake.source.isEmpty())
        self.assertEqual("", player.currentPlaybackSourcePath)
        self.assertEqual("none", player.currentPlaybackSourceType)

    def test_invalid_media_releases_backend_source_without_clearing_session(self):
        session, player, fake, _output = self._build_player()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "invalid.wav"
            source.write_bytes(b"invalid")
            session.setCurrentFile(str(source), "audio_editor")
            fake.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.InvalidMedia)

            self.assertEqual("error", player.playerState)
            self.assertTrue(fake.source.isEmpty())
            self.assertEqual(str(source.resolve()), session.currentFilePath)
            self.assertTrue(session.hasCurrentFile)


if __name__ == "__main__":
    unittest.main()

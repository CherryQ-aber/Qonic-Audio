import unittest

from PySide6.QtCore import QObject, Signal

from ui_next.bridge.lyrics_sync_viewmodel import LyricsSyncViewModel


class _EditSessionStub(QObject):
    stateChanged = Signal()

    def __init__(self, lyrics: str) -> None:
        super().__init__()
        self.draftLyrics = lyrics

    def set_lyrics(self, lyrics: str) -> None:
        self.draftLyrics = lyrics
        self.stateChanged.emit()


class _AudioPlayerStub(QObject):
    stateChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.position = 0
        self.hasPlaybackSource = True
        self.playbackMatchesEditorFile = True

    def set_position(self, position: int) -> None:
        self.position = position
        self.stateChanged.emit()


class LyricsSyncViewModelTests(unittest.TestCase):
    def setUp(self):
        self.edit_session = _EditSessionStub(
            "作词：CherryQ\n"
            "[00:01.000]Hello\n"
            "[00:01.000]你好\n"
            "[00:03.50]Next\n"
            "[00:05][00:07]Repeat"
        )
        self.player = _AudioPlayerStub()
        self.sync = LyricsSyncViewModel(self.edit_session, self.player)

    def test_timed_lines_group_translation_and_follow_player_clock(self):
        self.assertEqual(4, self.sync.lineCount)
        self.assertTrue(self.sync.hasTimedLyrics)
        self.assertTrue(self.sync.availableForPlayback)
        self.assertEqual(-1, self.sync.currentLineIndex)
        self.assertEqual("Hello", self.sync.nextLineText)

        self.player.set_position(1_000)
        self.assertEqual(1, self.sync.currentLineIndex)
        self.assertEqual("Hello", self.sync.currentLineText)
        self.assertEqual("你好", self.sync.currentLineTranslation)
        self.assertEqual("Next", self.sync.nextLineText)
        self.assertEqual(
            "[00:01.000]Hello\n[00:01.000]你好",
            self.edit_session.draftLyrics[
                self.sync.currentLineSourceStart:
                self.sync.currentLineSourceEnd
            ],
        )

        self.player.set_position(3_500)
        self.assertEqual(2, self.sync.currentLineIndex)
        self.assertEqual("Next", self.sync.currentLineText)

        self.player.set_position(6_500)
        self.assertEqual(3, self.sync.currentLineIndex)
        self.assertEqual("Repeat", self.sync.currentLineText)
        self.player.set_position(7_000)
        self.assertEqual(3, self.sync.currentLineIndex)

    def test_draft_and_player_identity_control_preview_availability(self):
        self.player.playbackMatchesEditorFile = False
        self.player.stateChanged.emit()
        self.assertFalse(self.sync.availableForPlayback)

        self.player.playbackMatchesEditorFile = True
        self.player.stateChanged.emit()
        self.assertTrue(self.sync.availableForPlayback)

        self.edit_session.set_lyrics("plain lyrics without timestamps")
        self.assertFalse(self.sync.hasTimedLyrics)
        self.assertFalse(self.sync.availableForPlayback)
        self.assertEqual(-1, self.sync.currentLineIndex)

    def test_scroll_follow_is_optional_and_session_scoped(self):
        changes = []
        self.sync.followEnabledChanged.connect(
            lambda: changes.append(self.sync.followEnabled)
        )
        self.assertTrue(self.sync.followEnabled)
        self.sync.setFollowEnabled(False)
        self.assertFalse(self.sync.followEnabled)
        self.sync.setFollowEnabled(False)
        self.sync.setFollowEnabled(True)
        self.assertEqual([False, True], changes)

    def test_playback_line_changes_do_not_reset_the_lines_model(self):
        line_model_changes = []
        playback_changes = []
        self.sync.linesChanged.connect(lambda: line_model_changes.append(True))
        self.sync.playbackLineChanged.connect(
            lambda: playback_changes.append(self.sync.currentLineIndex)
        )

        self.player.set_position(1_000)
        self.player.set_position(1_500)
        self.player.set_position(3_500)

        self.assertEqual([], line_model_changes)
        self.assertEqual([1, 2], playback_changes)

    def test_source_range_uses_qml_utf16_positions(self):
        self.edit_session.set_lyrics("😀 intro\n[00:01.000]Current")
        self.player.set_position(1_000)

        self.assertEqual(9, self.sync.currentLineSourceStart)
        self.assertEqual(27, self.sync.currentLineSourceEnd)


if __name__ == "__main__":
    unittest.main()

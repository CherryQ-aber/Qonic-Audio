import os
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QmlNative2kWindowLayoutTests(unittest.TestCase):
    def _source(self, path: str) -> str:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")

    def test_shell_uses_remaining_workspace_and_single_preview_badge(self):
        shell = self._source("ui_next/qml/AppShell.qml")
        header = self._source("ui_next/qml/components/TopStatusBar.qml")

        self.assertIn("Layout.minimumWidth: 0", shell)
        self.assertIn("capabilityLabel: capabilityGate.previewMode", shell)
        self.assertIn("WorkspaceSubNavigation {", shell)
        self.assertIn("WorkspaceStack {", shell)
        self.assertIn("FolderBrowserPane {", shell)
        self.assertIn("root.capabilityLabel.length > 0", header)
        self.assertIn("ScrollView", self._source("ui_next/qml/components/RightInspector.qml"))

    def test_primary_pages_use_viewport_width_and_vertical_scroll(self):
        for path in (
            "ui_next/qml/pages/AudioEditorPage.qml",
            "ui_next/qml/pages/MetadataPage.qml",
            "ui_next/qml/pages/LyricsCoverPage.qml",
        ):
            source = self._source(path)
            self.assertIn("Flickable {", source, path)
            self.assertIn("contentWidth: width", source, path)
            self.assertIn("ScrollBar.vertical", source, path)
            self.assertIn("Layout.minimumWidth: 0", source, path)

        settings = self._source("ui_next/qml/pages/SettingsPage.qml")
        self.assertIn("width: pageScroll.width", settings)
        self.assertIn("contentHeight: settingsContent.implicitHeight", settings)
        self.assertNotIn("Math.max(860", settings)
        self.assertIn("component SettingRow: ColumnLayout", settings)

    def test_cards_that_previously_overflow_now_wrap_or_size_to_content(self):
        metadata = self._source("ui_next/qml/pages/MetadataPage.qml")
        lyrics = self._source("ui_next/qml/pages/LyricsCoverPage.qml")
        editor = self._source("ui_next/qml/pages/AudioEditorPage.qml")

        self.assertIn("pageScroll.width >= 880 ? 3", metadata)
        self.assertIn("pageScroll.width >= 660 ? 2 : 1", metadata)
        self.assertIn('objectName: "lyricsCoverLyricsPreview"', lyrics)
        self.assertNotIn("CoverDraftEditor {", lyrics)
        self.assertNotIn("LyricsSourceBadge {", lyrics)
        self.assertIn('objectName: "lyricsWorkspaceGrid"', lyrics)
        self.assertNotIn("Layout.fillHeight: true", editor)

        processing = self._source("ui_next/qml/pages/AudioProcessingPage.qml")
        pitch = self._source("ui_next/qml/components/PitchShiftCard.qml")
        preview = self._source("ui_next/qml/components/PreviewCachePanel.qml")
        export = self._source("ui_next/qml/components/ExportResultPanel.qml")
        metadata_form = self._source("ui_next/qml/components/MetadataForm.qml")
        cover = self._source("ui_next/qml/components/CoverPreviewCard.qml")
        self.assertIn("implicitHeight: processingContent.implicitHeight", processing)
        self.assertIn("implicitHeight: pitchContent.implicitHeight", pitch)
        self.assertIn("columns: root.width >= 900 ? 3 : 1", pitch)
        self.assertIn("implicitHeight: previewContent.implicitHeight", preview)
        self.assertIn("implicitHeight: exportContent.implicitHeight", export)
        self.assertIn("implicitHeight: metadataContent.implicitHeight", metadata_form)
        self.assertIn("implicitHeight: coverContent.implicitHeight", cover)

    def test_offscreen_geometry_smoke_loads_all_repaired_pages(self):
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        for module in (
            "autoConvert",
            "audioEditor",
            "metadata",
            "lyricsCover",
            "audioProcessing",
            "analysis",
            "settings",
        ):
            completed = subprocess.run(
                [sys.executable, "-B", "main_qml.py", "--qml-smoke-test", f"--qml-open-module={module}"],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertNotIn("Unexpected token", completed.stdout + completed.stderr)
            self.assertNotIn("ReferenceError", completed.stdout + completed.stderr)

        settings_overlay = subprocess.run(
            [
                sys.executable,
                "-B",
                "main_qml.py",
                "--qml-smoke-test",
                "--qml-open-settings",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(
            settings_overlay.returncode,
            0,
            settings_overlay.stdout + settings_overlay.stderr,
        )
        self.assertNotIn(
            "ReferenceError",
            settings_overlay.stdout + settings_overlay.stderr,
        )


if __name__ == "__main__":
    unittest.main()

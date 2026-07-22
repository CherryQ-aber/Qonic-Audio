import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root
    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property var editSession: null
    property bool pageActive: true
    property bool splitLyricsWorkspace: pageScroll.width >= 720

    onPageActiveChanged: {
        if (!pageActive && sourceDiscardDialog.visible)
            sourceDiscardDialog.close()
        if (!pageActive && lrcOverwriteDialog.visible)
            lrcOverwriteDialog.close()
    }

    function requestManualSource() {
        if (!editSession || !fileSessionViewModel)
            return
        if (editSession.lyricsDirty) {
            sourceDiscardDialog.open()
            return
        }
        fileSessionViewModel.chooseLyricsFile()
    }
    function requestEmbeddedLyricsExport() {
        if (editSession)
            editSession.chooseLyricsAudioExport(false)
    }
    function requestAudioExport() {
        if (editSession)
            editSession.openUnifiedExportDialog("lyrics")
    }
    function pageSafetyMessage() {
        if (editSession && editSession.hasSession) return "当前歌词修改仅保存在内存中；导出可生成新文件，覆盖 .lrc 时会再次确认。"
        return lyricsViewModel.lyricsReadEnabled ? "歌词可供查看和编辑；外置 .lrc 会先载入草稿。" : "预览模式不会读取真实歌词。"
    }
    function pageCapabilityLabel() {
        if (lyricsViewModel.lyricsReadEnabled) return "歌词已就绪"
        return "预览模式"
    }
    function pageHasLiveCapability() { return lyricsViewModel.lyricsReadEnabled }
    function resetPageScrollIfContentFits() {
        if (pageScroll.contentHeight <= pageScroll.height + 0.5
                && pageScroll.contentY !== 0) {
            pageScroll.contentY = 0
        }
    }

    Flickable {
        id: pageScroll
        objectName: "lyricsCoverPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: Math.max(height, pageContent.implicitHeight)
        boundsBehavior: Flickable.StopAtBounds
        onHeightChanged: root.resetPageScrollIfContentFits()
        onContentHeightChanged: root.resetPageScrollIfContentFits()
        ScrollBar.vertical: ThemeScrollBar {
            objectName: "lyricsCoverPageVerticalScrollBar"
            theme: root.theme
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: pageContent
            objectName: "lyricsCoverPageContent"
            width: pageScroll.width
            Layout.minimumWidth: 0
            spacing: root.theme.spacing

            SectionCard {
                id: compactHeader
                objectName: "lyricsCoverSafetyCard"
                Layout.fillWidth: true; Layout.minimumWidth: 0
                tone: root.pageHasLiveCapability() ? "normal" : "warning"
                implicitHeight: headerContent.implicitHeight + root.theme.spacing * 2
                ColumnLayout {
                    id: headerContent
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: root.theme.spacing
                    spacing: 7
                    Flow {
                        Layout.fillWidth: true; spacing: 8
                        StatusBadge { theme: root.theme; typography: root.typography; label: root.pageCapabilityLabel(); tone: root.pageHasLiveCapability() ? "accent" : "muted" }
                        StatusBadge { visible: root.audioPlayer && root.audioPlayer.playerState === "playing"; theme: root.theme; typography: root.typography; label: "当前文件播放中"; tone: "success" }
                        StatusBadge {
                            theme: root.theme
                            typography: root.typography
                            label: root.editSession
                                ? root.editSession.lyricsDraftStatusLabel : "等待读取"
                            tone: !root.editSession || !root.editSession.hasSession ? "muted"
                                : root.editSession.lyricsDraftStatusLabel === "导入歌词" ? "accent"
                                : root.editSession.lyricsDraftStatusLabel === "已修改歌词" ? "warning"
                                : "muted"
                        }
                    }
                    Text {
                        text: (fileSessionViewModel.currentFilePath === ""
                            ? "当前文件：尚未导入"
                            : "当前文件：" + fileSessionViewModel.currentFileName)
                            + " · 来源：" + (lyricsViewModel.lyricsSource || "无")
                            + " · " + lyricsViewModel.lineCount + " 行"
                            + " · 时间戳：" + (lyricsViewModel.hasTimestamps ? "有" : "无")
                        color: root.theme.textSecondary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                        maximumLineCount: 1
                    }
                    Text {
                        text: fileSessionViewModel.currentFilePath === ""
                            ? root.pageSafetyMessage()
                            : lyricsViewModel.lineCount === 0
                                && !(root.editSession && root.editSession.lyricsDirty)
                                ? "当前文件没有歌词；可导入 .lrc 或在正文区域创建草稿。"
                                : lyricsViewModel.statusMessage
                        color: fileSessionViewModel.currentFilePath === ""
                            ? root.theme.warning : root.theme.textPrimary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }
            }

            GridLayout {
                id: lyricsWorkspace
                objectName: "lyricsWorkspaceGrid"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredHeight: root.splitLyricsWorkspace
                    ? Math.max(470, pageScroll.height
                        - compactHeader.implicitHeight - root.theme.spacing)
                    : 920
                columns: root.splitLyricsWorkspace ? 2 : 1
                columnSpacing: root.theme.spacing
                rowSpacing: root.theme.spacing

                LyricsPreviewList {
                    objectName: "lyricsCoverLyricsPreview"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 0
                    Layout.minimumHeight: 260
                    Layout.preferredWidth: root.splitLyricsWorkspace
                        ? (lyricsWorkspace.width - root.theme.spacing) * 0.36
                        : lyricsWorkspace.width
                    theme: root.theme
                    typography: root.typography
                    lines: lyricsViewModel.lyricsLines
                    mockCurrentLine: lyricsViewModel.isMockPreview && lyricsViewModel.lineCount > 1 ? 1 : -1
                }

                LyricsDraftEditor {
                    objectName: "lyricsCoverDraftEditor"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 0
                    Layout.minimumHeight: 470
                    Layout.preferredWidth: root.splitLyricsWorkspace
                        ? (lyricsWorkspace.width - root.theme.spacing) * 0.64
                        : lyricsWorkspace.width
                    theme: root.theme
                    typography: root.typography
                    audioPlayer: root.audioPlayer
                    editSession: root.editSession
                    onManualSourceRequested: root.requestManualSource()
                    onEmbeddedLyricsExportRequested: root.requestEmbeddedLyricsExport()
                    onAudioExportRequested: root.requestAudioExport()
                    onLrcExportRequested: if (root.editSession) root.editSession.chooseLrcExport()
                    onLrcOverwriteRequested: lrcOverwriteDialog.open()
                }
            }
        }
    }

    Dialog {
        id: sourceDiscardDialog
        modal: true
        title: "放弃当前歌词修改？"
        standardButtons: Dialog.NoButton
        anchors.centerIn: parent
        width: Math.min(420, root.width - root.theme.spacing * 4)
        contentItem: ColumnLayout {
            spacing: root.theme.spacing
            Text { text: "导入新的 .lrc 会替换当前内存中的歌词修改；磁盘文件不会在此步骤被改动。"; color: root.theme.textPrimary; font.family: root.typography.fontFamily; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "取消"; onClicked: sourceDiscardDialog.close() }
                Button {
                    text: "放弃并继续"
                    onClicked: {
                        sourceDiscardDialog.close()
                        root.editSession.restoreOriginalLyrics()
                        fileSessionViewModel.chooseLyricsFile()
                    }
                }
            }
        }
    }

    Dialog {
        id: lrcOverwriteDialog
        objectName: "lrcOverwriteDialog"
        modal: true
        title: "确认覆盖当前 .lrc？"
        standardButtons: Dialog.NoButton
        anchors.centerIn: parent
        width: Math.min(460, root.width - root.theme.spacing * 4)
        contentItem: ColumnLayout {
            spacing: root.theme.spacing
            Text {
                text: "将用当前歌词覆盖这一个 .lrc 文件：\n"
                    + (root.editSession ? root.editSession.selectedLyricsLrcPath : "")
                    + "\n\n音频源文件不会修改。"
                color: root.theme.textPrimary
                font.family: root.typography.fontFamily
                wrapMode: Text.WrapAnywhere
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "取消"; onClicked: lrcOverwriteDialog.close() }
                Button {
                    text: "确认覆盖"
                    enabled: root.editSession && root.editSession.canOverwriteCurrentLrc
                    onClicked: {
                        lrcOverwriteDialog.close()
                        root.editSession.overwriteCurrentLrc()
                    }
                }
            }
        }
    }

}

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
    }

    function requestSource(source) {
        if (!editSession)
            return
        if (editSession.selectLyricsSource(source, false) === "unsaved_changes") {
            sourceDiscardDialog.source = source
            sourceDiscardDialog.manual = false
            sourceDiscardDialog.open()
        }
    }
    function requestManualSource() {
        if (!editSession || !fileSessionViewModel)
            return
        if (editSession.lyricsDirty) {
            sourceDiscardDialog.manual = true
            sourceDiscardDialog.open()
            return
        }
        fileSessionViewModel.chooseLyricsFile()
    }
    function requestAudioExport() {
        if (editSession)
            editSession.openUnifiedExportDialog("lyrics")
    }
    function pageSafetyMessage() {
        if (editSession && editSession.hasSession) return "当前歌词修改仅保存在内存草稿中；导出只会生成新的音频副本或新的 .lrc 文件。"
        return lyricsViewModel.lyricsReadEnabled ? "歌词可供查看和编辑；外置 .lrc 会先载入草稿。" : "预览模式不会读取真实歌词。"
    }
    function pageCapabilityLabel() {
        if (lyricsViewModel.lyricsReadEnabled) return "歌词已就绪"
        return "预览模式"
    }
    function pageHasLiveCapability() { return lyricsViewModel.lyricsReadEnabled }

        Flickable {
            id: pageScroll
            objectName: "lyricsCoverPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: pageContent.implicitHeight + root.theme.spacing * 2
        boundsBehavior: Flickable.StopAtBounds
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
                            label: root.editSession && root.editSession.lyricsDirty
                                ? "歌词草稿已修改" : "歌词草稿未修改"
                            tone: root.editSession && root.editSession.lyricsDirty ? "warning" : "muted"
                        }
                        ActionButton { text: "选择 .lrc 作为草稿来源"; onClicked: root.requestManualSource() }
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
                    ? Math.max(470, pageScroll.height - compactHeader.implicitHeight - root.theme.spacing * 2)
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
                    editSession: root.editSession
                    onSourceRequested: function(source) { root.requestSource(source) }
                    onManualSourceRequested: root.requestManualSource()
                    onAudioExportRequested: root.requestAudioExport()
                    onLrcExportRequested: if (root.editSession) root.editSession.chooseLrcExport()
                }
            }
            Item { Layout.minimumHeight: root.theme.spacing }
        }
    }

    Dialog {
        id: sourceDiscardDialog
        property string source: ""
        property bool manual: false
        modal: true
        title: "放弃当前歌词草稿？"
        standardButtons: Dialog.NoButton
        anchors.centerIn: parent
        width: Math.min(420, root.width - root.theme.spacing * 4)
        contentItem: ColumnLayout {
            spacing: root.theme.spacing
            Text { text: "当前歌词有未导出的修改。切换来源会丢弃这些内存草稿，磁盘文件不会修改。"; color: root.theme.textPrimary; font.family: root.typography.fontFamily; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "取消"; onClicked: sourceDiscardDialog.close() }
                Button {
                    text: "放弃并继续"
                    onClicked: {
                        sourceDiscardDialog.close()
                        if (sourceDiscardDialog.manual) {
                            root.editSession.restoreOriginalLyrics()
                            fileSessionViewModel.chooseLyricsFile()
                        } else {
                            root.editSession.selectLyricsSource(sourceDiscardDialog.source, true)
                        }
                    }
                }
            }
        }
    }

    component ActionButton: Button {
        implicitHeight: 31; implicitWidth: 142
        font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall
        contentItem: Text { text: parent.text; color: parent.enabled ? root.theme.textPrimary : root.theme.muted; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; maximumLineCount: 1 }
        background: Rectangle { color: parent.enabled ? root.theme.surface : Qt.rgba(root.theme.surface.r, root.theme.surface.g, root.theme.surface.b, 0.55); border.color: parent.enabled ? root.theme.border : Qt.rgba(root.theme.border.r, root.theme.border.g, root.theme.border.b, 0.55); radius: root.theme.radiusSmall }
    }
    component DisabledAction: ActionButton { enabled: false; implicitWidth: 126; implicitHeight: 28; font.pixelSize: root.typography.sizeTiny }
}

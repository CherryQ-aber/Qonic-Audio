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
    property var lyricsSync: null
    property bool pageActive: true
    property bool splitLyricsWorkspace: pageScroll.width >= 720

    onPageActiveChanged: {
        if (!pageActive && sourceDiscardDialog.visible)
            sourceDiscardDialog.close()
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
            visible: size < 0.999
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
                theme: root.theme
                Layout.fillWidth: true; Layout.minimumWidth: 0
                implicitHeight: headerContent.implicitHeight + root.theme.spacing * 2
                RowLayout {
                    id: headerContent
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: root.theme.spacing
                    spacing: root.theme.spacing
                    Text {
                        text: (fileSessionViewModel.currentFilePath === ""
                            ? "当前文件：尚未导入"
                            : "当前文件：" + fileSessionViewModel.currentFileName)
                            + " · 来源：" + (lyricsViewModel.lyricsSource || "无")
                            + " · " + (root.editSession
                                ? root.editSession.lyricsLineCount
                                : lyricsViewModel.lineCount) + " 行"
                            + " · 时间戳：" + ((root.editSession
                                ? root.editSession.lyricsHasTimestamps
                                : lyricsViewModel.hasTimestamps) ? "有" : "无")
                        color: root.theme.textSecondary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                        maximumLineCount: 1
                    }
                    StatusBadge {
                        visible: root.editSession && root.editSession.lyricsDirty
                        theme: root.theme
                        typography: root.typography
                        label: "未保存"
                        tone: "warning"
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
                    lines: root.lyricsSync
                        ? root.lyricsSync.lines : lyricsViewModel.lyricsLines
                    currentLineIndex: root.lyricsSync
                        ? root.lyricsSync.currentLineIndex : -1
                    followCurrentLine: root.lyricsSync
                        ? root.lyricsSync.followEnabled : true
                    mockCurrentLine: !root.lyricsSync
                        && lyricsViewModel.isMockPreview
                        && lyricsViewModel.lineCount > 1 ? 1 : -1
                    onFollowCurrentLineRequested: function(enabled) {
                        if (root.lyricsSync)
                            root.lyricsSync.setFollowEnabled(enabled)
                    }
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
                    lyricsSync: root.lyricsSync
                    onManualSourceRequested: root.requestManualSource()
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

}

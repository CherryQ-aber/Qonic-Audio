import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property var editSession: null
    property var lyricsSync: null
    property int rememberedCursorPosition: 0
    property int rememberedSelectionStart: 0
    property int rememberedSelectionEnd: 0
    readonly property bool playbackLineAvailable: Boolean(
        lyricsSync
        && lyricsSync.availableForPlayback
        && lyricsSync.currentLineIndex >= 0
    )
    readonly property int playbackLineStart: playbackLineAvailable
        ? lyricsSync.currentLineSourceStart : -1
    readonly property int playbackLineEnd: playbackLineAvailable
        ? lyricsSync.currentLineSourceEnd : -1
    readonly property real draftViewportOffsetY:
        draftScrollView.contentItem
        ? draftScrollView.contentItem.contentY : 0
    readonly property rect playbackLineStartRect: {
        var editorWidth = draftEditor.width
        return draftEditor.positionToRectangle(
            Math.max(0, Math.min(playbackLineStart, draftEditor.length))
        )
    }
    readonly property rect playbackLineEndRect: {
        var editorWidth = draftEditor.width
        return draftEditor.positionToRectangle(
            Math.max(0, Math.min(playbackLineEnd, draftEditor.length))
        )
    }
    signal manualSourceRequested()
    signal embeddedLyricsExportRequested()
    signal lrcExportRequested()
    signal lrcOverwriteRequested()
    signal audioExportRequested()

    function rememberDraftSelection(force) {
        if (!force && !draftEditor.activeFocus) {
            return
        }
        rememberedCursorPosition = draftEditor.cursorPosition
        rememberedSelectionStart = draftEditor.selectionStart
        rememberedSelectionEnd = draftEditor.selectionEnd
    }

    function restoreDraftFocus() {
        Qt.callLater(function() {
            draftEditor.forceActiveFocus()
            draftEditor.cursorPosition = Math.min(
                rememberedCursorPosition,
                draftEditor.length
            )
            root.rememberDraftSelection(true)
        })
    }

    function insertCurrentTimestamp() {
        if (!editSession || !editSession.hasSession || editSession.lyricsExporting
                || !audioPlayer || !audioPlayer.hasPlaybackSource) {
            return
        }
        var result = editSession.insertLyricsTimestamp(
            rememberedSelectionStart,
            rememberedSelectionEnd,
            rememberedCursorPosition,
            audioPlayer.position,
            audioPlayer.timestampPrecision
        )
        if (!result || result.ok !== true) {
            return
        }
        Qt.callLater(function() {
            draftEditor.forceActiveFocus()
            var selectionStart = Number(result.selection_start)
            var selectionEnd = Number(result.selection_end)
            if (selectionStart !== selectionEnd) {
                draftEditor.select(selectionStart, selectionEnd)
            } else {
                draftEditor.cursorPosition = Number(result.cursor_position)
            }
            root.rememberDraftSelection(true)
        })
    }

    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall
    implicitHeight: 500

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: 7

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "歌词编辑"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
            }
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

        Flow {
            Layout.fillWidth: true
            spacing: 8
            Button {
                id: importLrcButton
                objectName: "importLrcButton"
                text: "导入 .lrc"
                enabled: root.editSession && root.editSession.hasSession
                    && !root.editSession.anyExporting
                onClicked: root.manualSourceRequested()
            }
            Button {
                id: exportMenuButton
                objectName: "lyricsExportMenuButton"
                text: "导出"
                enabled: root.editSession && root.editSession.hasSession
                    && root.editSession.lyricsDirty
                    && !root.editSession.anyExporting
                onClicked: exportMenu.popup()
            }
            Button {
                id: undoButton
                objectName: "undoLyricsButton"
                text: "撤回"
                enabled: root.editSession && root.editSession.canUndoLyrics
                onPressed: root.rememberDraftSelection(false)
                onClicked: {
                    root.editSession.undoLyricsDraft()
                    root.restoreDraftFocus()
                }
            }
            Button {
                id: insertTimestampButton
                objectName: "insertCurrentTimestampButton"
                text: "插入时间点"
                enabled: root.editSession && root.editSession.hasSession
                    && !root.editSession.lyricsExporting
                    && root.audioPlayer && root.audioPlayer.hasPlaybackSource
                onPressed: root.rememberDraftSelection(false)
                onClicked: root.insertCurrentTimestamp()
            }
        }

        ColumnLayout {
            id: currentLyricsPane
            objectName: "currentLyricsPane"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            Layout.minimumHeight: 230
            spacing: 5

            Text {
                text: "当前歌词"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                font.weight: typography.weightBold
                Layout.fillWidth: true
            }

            ScrollView {
                id: draftScrollView
                objectName: "lyricsDraftScrollView"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 180
                Layout.rightMargin: root.theme.spacing
                clip: true
                rightPadding: draftLyricsVerticalScrollBar.width + 4
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ThemeScrollBar {
                    id: draftLyricsVerticalScrollBar
                    objectName: "draftLyricsVerticalScrollBar"
                    parent: draftScrollView
                    anchors.top: draftScrollView.top
                    anchors.right: draftScrollView.right
                    anchors.bottom: draftScrollView.bottom
                    anchors.margins: 2
                    z: 2
                    theme: root.theme
                    policy: ScrollBar.AlwaysOn
                }
                background: Rectangle {
                    color: theme.inputBackground
                    border.color: draftEditor.activeFocus
                        ? theme.focusRing : theme.borderNormal
                    border.width: draftEditor.activeFocus ? 2 : 1
                    radius: theme.radiusSmall
                }

                TextArea {
                    id: draftEditor
                    objectName: "lyricsDraftTextArea"
                    width: draftScrollView.availableWidth
                    height: Math.max(implicitHeight, draftScrollView.availableHeight)
                    enabled: root.editSession && root.editSession.hasSession
                        && !root.editSession.lyricsExporting
                    text: root.editSession ? root.editSession.draftLyrics : ""
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    font.family: "Consolas"
                    font.pixelSize: typography.sizeBody
                    color: theme.textPrimary
                    placeholderText: "可输入普通歌词或保留 LRC 时间戳。"
                    placeholderTextColor: theme.textMuted
                    onCursorPositionChanged: root.rememberDraftSelection(false)
                    onSelectionStartChanged: root.rememberDraftSelection(false)
                    onSelectionEndChanged: root.rememberDraftSelection(false)
                    onTextChanged: if (activeFocus && root.editSession)
                        root.editSession.updateLyricsDraft(text)
                    background: Item {
                        Rectangle {
                            id: draftCurrentLineHighlight
                            objectName: "draftCurrentLineHighlight"
                            visible: root.playbackLineAvailable
                                && root.playbackLineStart >= 0
                                && root.playbackLineEnd
                                    >= root.playbackLineStart
                            x: draftEditor.leftPadding
                            y: root.playbackLineStartRect.y
                                - root.draftViewportOffsetY
                            width: Math.max(
                                0,
                                draftEditor.width
                                    - draftEditor.leftPadding
                                    - draftEditor.rightPadding
                            )
                            height: Math.max(
                                root.playbackLineStartRect.height,
                                root.playbackLineEndRect.y
                                    - root.playbackLineStartRect.y
                                    + root.playbackLineEndRect.height
                            )
                            color: Qt.rgba(
                                theme.warning.r,
                                theme.warning.g,
                                theme.warning.b,
                                0.16
                            )
                            border.color: Qt.rgba(
                                theme.warning.r,
                                theme.warning.g,
                                theme.warning.b,
                                0.72
                            )
                            border.width: 1
                            radius: theme.radiusSmall
                        }
                    }
                }
            }
        }

        Text {
            text: root.editSession ? root.editSession.statusMessage : ""
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }
        Text {
            visible: root.editSession
                && root.editSession.unifiedExportMessage.length > 0
            text: root.editSession
                ? "音频副本：" + root.editSession.unifiedExportMessage : ""
            color: root.editSession
                && root.editSession.unifiedExportResult.success === true
                ? theme.success : theme.warning
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
        Text {
            visible: !!(root.editSession
                && root.editSession.lastLyricsExportResult.applied_operations
                && root.editSession.lastLyricsExportResult.applied_operations.length === 1
                && root.editSession.lastLyricsExportResult.applied_operations[0] === "lrc")
            text: root.editSession
                ? "独立 LRC：" + root.editSession.lastLyricsExportMessage : ""
            color: root.editSession
                && root.editSession.lastLyricsExportResult.success === true
                ? theme.success : theme.warning
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
    }

    Menu {
        id: exportMenu
        objectName: "lyricsExportMenu"

        Action {
            text: "嵌入歌词"
            enabled: root.editSession && root.editSession.lyricsDirty
                && !root.editSession.anyExporting
            onTriggered: root.embeddedLyricsExportRequested()
        }
        Action {
            text: "另存 .lrc 文件"
            enabled: root.editSession && root.editSession.lyricsDirty
                && !root.editSession.anyExporting
            onTriggered: root.lrcExportRequested()
        }
        Action {
            text: "覆盖 .lrc 文件"
            enabled: root.editSession && root.editSession.canOverwriteCurrentLrc
            onTriggered: root.lrcOverwriteRequested()
        }
        MenuSeparator {}
        Action {
            text: "导出音频副本"
            enabled: root.editSession && root.editSession.lyricsDirty
                && !root.editSession.anyExporting
            onTriggered: root.audioExportRequested()
        }
    }
}

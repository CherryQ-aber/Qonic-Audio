import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var editSession: null
    signal sourceRequested(string source)
    signal manualSourceRequested()
    signal audioExportRequested()
    signal lrcExportRequested()

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
                text: "歌词编辑（草稿）"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
            }
            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: !root.editSession || !root.editSession.hasSession ? "等待读取"
                    : root.editSession.lyricsDirty ? "有未导出修改" : "草稿未修改"
                tone: root.editSession && root.editSession.lyricsDirty ? "warning" : "muted"
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8
            Button { text: "内嵌歌词"; visible: root.editSession && root.editSession.hasEmbeddedLyricsSource; onClicked: root.sourceRequested("embedded") }
            Button { text: "同名 LRC"; visible: root.editSession && root.editSession.hasSiblingLrcSource; onClicked: root.sourceRequested("sibling_lrc") }
            Button { text: "选择 .lrc 作为草稿来源"; onClicked: root.manualSourceRequested() }
        }

        GridLayout {
            id: lyricsBodyGrid
            objectName: "lyricsBodyGrid"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 230
            columns: width >= 660 ? 2 : 1
            columnSpacing: root.theme.spacing
            rowSpacing: 7

            ColumnLayout {
                objectName: "originalLyricsPane"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                Layout.minimumHeight: lyricsBodyGrid.columns === 1 ? 90 : 230
                spacing: 5
                Text {
                    text: "原始歌词预览"
                    color: theme.textPrimary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    font.weight: typography.weightBold
                    Layout.fillWidth: true
                }
                ScrollView {
                    id: originalLyricsScrollView
                    objectName: "originalLyricsScrollView"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 64
                    Layout.rightMargin: root.theme.spacing
                    clip: true
                    rightPadding: originalLyricsVerticalScrollBar.width + 4
                    contentWidth: availableWidth
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical: ThemeScrollBar {
                        id: originalLyricsVerticalScrollBar
                        objectName: "originalLyricsVerticalScrollBar"
                        parent: originalLyricsScrollView
                        anchors.top: originalLyricsScrollView.top
                        anchors.right: originalLyricsScrollView.right
                        anchors.bottom: originalLyricsScrollView.bottom
                        anchors.margins: 2
                        z: 2
                        theme: root.theme
                        policy: ScrollBar.AlwaysOn
                    }
                    background: Rectangle {
                        color: theme.inputBackground
                        border.color: theme.borderNormal
                        radius: theme.radiusSmall
                    }

                    TextArea {
                        objectName: "originalLyricsTextArea"
                        width: originalLyricsScrollView.availableWidth
                        height: Math.max(implicitHeight, originalLyricsScrollView.availableHeight)
                        readOnly: true
                        selectByMouse: true
                        text: root.editSession ? root.editSession.originalLyrics : ""
                        wrapMode: TextEdit.Wrap
                        font.family: "Consolas"
                        font.pixelSize: typography.sizeSmall
                        color: theme.textPrimary
                        background: null
                    }
                }
            }

            ColumnLayout {
                objectName: "draftLyricsPane"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                Layout.minimumHeight: lyricsBodyGrid.columns === 1 ? 140 : 230
                spacing: 5
                Text {
                    text: "当前草稿"
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
                    Layout.minimumHeight: 104
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
                        border.color: draftEditor.activeFocus ? theme.focusRing : theme.borderNormal
                        border.width: draftEditor.activeFocus ? 2 : 1
                        radius: theme.radiusSmall
                    }

                    TextArea {
                        id: draftEditor
                        objectName: "lyricsDraftTextArea"
                        width: draftScrollView.availableWidth
                        height: Math.max(implicitHeight, draftScrollView.availableHeight)
                        enabled: root.editSession && root.editSession.hasSession && !root.editSession.lyricsExporting
                        text: root.editSession ? root.editSession.draftLyrics : ""
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        font.family: "Consolas"
                        font.pixelSize: typography.sizeBody
                        color: theme.textPrimary
                        placeholderText: "可输入普通歌词或保留 LRC 时间戳。"
                        placeholderTextColor: theme.textMuted
                        onTextChanged: if (activeFocus && root.editSession) root.editSession.updateLyricsDraft(text)
                        background: null
                    }
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8
            Button { text: "保存内存草稿"; enabled: root.editSession && root.editSession.hasSession; onClicked: root.editSession.saveLyricsDraft() }
            Button { text: "恢复原始歌词"; enabled: root.editSession && root.editSession.lyricsDirty; onClicked: root.editSession.restoreOriginalLyrics() }
            Button { text: "清空草稿"; enabled: root.editSession && root.editSession.hasSession; onClicked: root.editSession.clearLyricsDraft() }
            Button { text: "导出到音频副本"; enabled: root.editSession && root.editSession.lyricsDirty && !root.editSession.lyricsExporting; onClicked: root.audioExportRequested() }
            Button { text: "另存为 .lrc"; enabled: root.editSession && root.editSession.lyricsDirty && !root.editSession.lyricsExporting; onClicked: root.lrcExportRequested() }
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
            visible: root.editSession && root.editSession.unifiedExportMessage.length > 0
            text: root.editSession ? "音频副本：" + root.editSession.unifiedExportMessage : ""
            color: root.editSession && root.editSession.unifiedExportResult.success === true ? theme.success : theme.warning
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
        Text {
            visible: !!(root.editSession && root.editSession.lastLyricsExportResult.applied_operations
                && root.editSession.lastLyricsExportResult.applied_operations.length === 1
                && root.editSession.lastLyricsExportResult.applied_operations[0] === "lrc"
            )
            text: root.editSession ? "独立 LRC：" + root.editSession.lastLyricsExportMessage : ""
            color: root.editSession && root.editSession.lastLyricsExportResult.success === true ? theme.success : theme.warning
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
    }
}

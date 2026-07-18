import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var fileSession: null
    property var editSession: null
    property var audioPlayer: null
    property var processingSession: null

    function sessionStateLabel(state) {
        if (state === "loading")
            return "正在读取"
        if (state === "ready")
            return "已就绪"
        if (state === "partial")
            return "部分信息不可用"
        if (state === "missing")
            return "源文件已不可用"
        if (state === "error")
            return "读取失败"
        return "空会话"
    }

    function draftSummary() {
        if (!root.editSession || !root.editSession.hasSession)
            return "当前没有编辑草稿"
        if (!root.editSession.hasUnsavedDrafts)
            return "没有未导出的修改"
        return "未导出：" + root.editSession.unsavedDraftLabels.join("、")
    }

    implicitHeight: content.implicitHeight + theme.spacing * 2
    color: theme.panel
    border.color: theme.border
    border.width: 1
    radius: theme.radiusSmall

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.theme.spacing
        spacing: 7

        GridLayout {
            id: currentFileSummaryGrid
            objectName: "currentFileSummaryGrid"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            columns: width >= 720 ? 2 : 1
            columnSpacing: root.theme.spacing
            rowSpacing: 6

            FileSummaryRow {
                label: "当前编辑文件"
                value: root.fileSession && root.fileSession.hasCurrentFile
                    ? root.fileSession.currentFileName : "未导入音频"
                strong: true
            }
            FileSummaryRow {
                label: "读取状态"
                value: root.fileSession
                    ? root.sessionStateLabel(root.fileSession.sessionState) : "空会话"
            }
            FileSummaryRow {
                Layout.columnSpan: currentFileSummaryGrid.columns
                label: "文件路径"
                value: root.fileSession && root.fileSession.hasCurrentFile
                    ? root.fileSession.currentFilePath : "未选择"
                middleElide: true
            }
            FileSummaryRow {
                label: "文件来源"
                value: root.fileSession && root.fileSession.hasCurrentFile
                    ? root.fileSession.currentFileSourceLabel : "未选择"
            }
            FileSummaryRow {
                label: "文件格式"
                value: root.fileSession && root.fileSession.hasCurrentFile
                    ? root.fileSession.currentFileFormat : "-"
            }
            FileSummaryRow {
                Layout.columnSpan: currentFileSummaryGrid.columns
                label: "当前播放源"
                value: root.audioPlayer
                    ? root.audioPlayer.currentPlaybackSourceTypeLabel
                        + " · " + root.audioPlayer.currentPlaybackSourceLabel
                    : "未加载"
                middleElide: true
            }
            FileSummaryRow {
                Layout.columnSpan: currentFileSummaryGrid.columns
                label: "草稿状态"
                value: root.draftSummary()
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.fileSession && root.fileSession.hasCurrentFile
                    ? (root.fileSession.currentFileExists ? "工作区已载入" : "源文件不可用")
                    : "未加载"
                tone: root.fileSession && root.fileSession.hasCurrentFile && root.fileSession.currentFileExists
                    ? "accent"
                    : "muted"
            }
            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.editSession && root.editSession.hasUnsavedDrafts
                    ? "有未导出草稿"
                    : "原文件保持不变"
                tone: root.editSession && root.editSession.hasUnsavedDrafts ? "warning" : "muted"
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            FileActionButton { text: "导入音频"; enabled: root.fileSession && root.fileSession.realFileAccessEnabled; onClicked: root.fileSession.chooseAudioFile("audio_editor") }
            FileActionButton { text: "导入 .lrc 草稿"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: root.fileSession.chooseLyricsFile() }
            FileActionButton { text: "清除当前音频"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: root.fileSession.clearCurrentFile() }
            FileActionButton { text: "重新读取"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: root.fileSession.reloadCurrentFile() }
            FileActionButton { text: "查看文件信息"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: appState.switchModule("metadata") }
            FileActionButton { text: "查看歌词"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: appState.switchModule("lyricsCover") }
            FileActionButton { text: "导出编辑副本"; enabled: root.editSession && root.editSession.hasUnsavedDrafts && !root.editSession.anyExporting; onClicked: root.editSession.openUnifiedExportDialog("auto") }
            FileActionButton { text: "前往单文件转换"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: appState.switchModule("autoConvert") }
            FileActionButton {
                text: "返回原音频"
                enabled: root.fileSession && root.fileSession.hasCurrentFile && root.audioPlayer
                onClicked: {
                    if (root.processingSession)
                        root.processingSession.returnToOriginal()
                    else
                        root.audioPlayer.returnToOriginal()
                }
            }
            FileActionButton { text: "打开文件位置"; enabled: root.fileSession && root.fileSession.hasCurrentFile; onClicked: root.fileSession.openCurrentFileLocation() }
        }
    }

    component FileSummaryRow: RowLayout {
        property string label: ""
        property string value: ""
        property bool strong: false
        property bool middleElide: false
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 8
        Text { text: parent.label; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.preferredWidth: 84 }
        Text { text: parent.value; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: parent.strong ? root.typography.sizeMedium : root.typography.sizeSmall; font.weight: parent.strong ? root.typography.weightBold : root.typography.weightRegular; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: parent.middleElide ? Text.ElideMiddle : Text.ElideRight; maximumLineCount: 1 }
    }

    component FileActionButton: Button {
        implicitWidth: 138
        implicitHeight: 30
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
        contentItem: Text { text: parent.text; color: parent.enabled ? root.theme.textPrimary : root.theme.muted; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; maximumLineCount: 1 }
        background: Rectangle { color: parent.enabled ? root.theme.surface : Qt.rgba(root.theme.muted.r, root.theme.muted.g, root.theme.muted.b, 0.08); border.color: parent.enabled ? root.theme.border : Qt.rgba(root.theme.border.r, root.theme.border.g, root.theme.border.b, 0.5); radius: root.theme.radiusSmall }
    }
}

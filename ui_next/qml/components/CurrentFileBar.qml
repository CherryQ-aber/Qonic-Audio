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
    property bool floatingMode: false
    property bool expanded: false
    readonly property string effectiveCoverSource: (
        root.editSession
        && root.editSession.hasSession
        && root.editSession.coverAction !== "remove"
    ) ? root.editSession.draftCoverPreviewUrl : ""

    signal collapseRequested()

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

    function playbackMatchLabel() {
        if (!root.fileSession || !root.fileSession.hasCurrentFile)
            return "未选择编辑文件"
        if (!root.audioPlayer || !root.audioPlayer.hasPlaybackSource)
            return "播放器未载入"
        return root.audioPlayer.playbackMatchesEditorFile
            ? "播放文件与编辑文件一致"
            : "播放文件与编辑文件不同"
    }

    function loadCurrentFileInPlayer() {
        if (!root.fileSession || !root.fileSession.hasCurrentFile || !root.audioPlayer)
            return
        root.audioPlayer.loadEditorFile(
            root.fileSession.currentFilePath,
            root.fileSession.sessionGeneration,
            "editor_file"
        )
    }

    implicitHeight: expandedContent.implicitHeight + theme.spacing * 2
    color: root.floatingMode ? theme.drawerBackground : theme.panel
    border.color: root.floatingMode ? theme.borderStrong : theme.border
    border.width: 1
    radius: root.floatingMode ? theme.radiusMedium : theme.radiusSmall
    clip: true

    ColumnLayout {
        id: expandedContent
        objectName: "currentFileBarExpandedContent"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.theme.spacing
        spacing: 7

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0

            Text {
                text: "当前编辑文件"
                color: root.theme.textSecondary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                font.weight: root.typography.weightBold
                Layout.fillWidth: true
            }

            FileActionButton {
                objectName: "collapseCurrentFileBarButton"
                visible: root.floatingMode
                implicitWidth: 82
                text: "收起"
                onClicked: root.collapseRequested()
            }
        }

        RowLayout {
            id: currentFileSummary
            objectName: "currentFileSummaryGrid"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: root.theme.spacing

            Rectangle {
                objectName: "currentEditCoverThumbnail"
                Layout.preferredWidth: 64
                Layout.preferredHeight: 64
                Layout.alignment: Qt.AlignTop
                color: root.theme.surface
                border.color: root.theme.border
                border.width: 1
                radius: root.theme.radiusSmall
                clip: true

                Image {
                    anchors.fill: parent
                    anchors.margins: 3
                    visible: root.effectiveCoverSource.length > 0
                    source: root.effectiveCoverSource
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    cache: false
                }

                Text {
                    anchors.centerIn: parent
                    visible: root.effectiveCoverSource.length === 0
                    text: "♫"
                    color: root.theme.muted
                    font.family: root.typography.fontFamily
                    font.pixelSize: 28
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 4

                Text {
                    text: root.fileSession && root.fileSession.hasCurrentFile
                        ? root.fileSession.currentFileName : "未导入音频"
                    color: root.theme.textPrimary
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeMedium
                    font.weight: root.typography.weightBold
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Text {
                    text: root.fileSession && root.fileSession.hasCurrentFile
                        ? root.fileSession.currentFilePath : "选择音频后开始编辑"
                    color: root.theme.textSecondary
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeSmall
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideMiddle
                    maximumLineCount: 1
                }

                Text {
                    text: root.fileSession && root.fileSession.hasCurrentFile
                        ? root.fileSession.currentFileFormat + " · "
                            + root.fileSession.currentFileSourceLabel + " · "
                            + root.sessionStateLabel(root.fileSession.sessionState)
                        : "空会话"
                    color: root.theme.muted
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeTiny
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            StatusBadge {
                objectName: "editorPlaybackMatchBadge"
                theme: root.theme
                typography: root.typography
                label: root.playbackMatchLabel()
                tone: root.audioPlayer && root.audioPlayer.hasPlaybackSource
                    ? (root.audioPlayer.playbackMatchesEditorFile ? "success" : "warning")
                    : "muted"
            }
            StatusBadge {
                objectName: "metadataDirtyBadge"
                theme: root.theme
                typography: root.typography
                label: root.editSession && root.editSession.dirty
                    ? "Metadata 已修改" : "Metadata 未修改"
                tone: root.editSession && root.editSession.dirty ? "warning" : "muted"
            }
            StatusBadge {
                objectName: "coverDirtyBadge"
                theme: root.theme
                typography: root.typography
                label: root.editSession && root.editSession.coverDirty
                    ? "封面已修改" : "封面未修改"
                tone: root.editSession && root.editSession.coverDirty ? "warning" : "muted"
            }
            StatusBadge {
                objectName: "lyricsDirtyBadge"
                theme: root.theme
                typography: root.typography
                label: root.editSession && root.editSession.lyricsDirty
                    ? "歌词已修改" : "歌词未修改"
                tone: root.editSession && root.editSession.lyricsDirty ? "warning" : "muted"
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            FileActionButton {
                objectName: "importEditorAudioButton"
                text: "导入音频"
                enabled: root.fileSession && root.fileSession.realFileAccessEnabled
                onClicked: root.fileSession.chooseAudioFile("audio_editor")
            }
            FileActionButton {
                objectName: "loadEditorFileInPlayerButton"
                text: "载入播放器"
                enabled: root.fileSession
                    && root.fileSession.hasCurrentFile
                    && root.audioPlayer
                    && root.audioPlayer.audioPlaybackEnabled
                onClicked: root.loadCurrentFileInPlayer()
            }
            FileActionButton {
                objectName: "openEditorFileLocationButton"
                text: "打开文件位置"
                enabled: root.fileSession && root.fileSession.hasCurrentFile
                onClicked: root.fileSession.openCurrentFileLocation()
            }
            FileActionButton {
                objectName: "exportEditorDraftsButton"
                text: "统一导出"
                enabled: root.editSession
                    && root.editSession.hasUnsavedDrafts
                    && !root.editSession.anyExporting
                onClicked: root.editSession.openUnifiedExportDialog("auto")
            }
            FileActionButton {
                objectName: "reloadEditorFileButton"
                text: "重新读取"
                enabled: root.fileSession && root.fileSession.hasCurrentFile
                onClicked: root.fileSession.reloadCurrentFile()
            }
            FileActionButton {
                objectName: "clearEditorFileButton"
                text: "清除"
                enabled: root.fileSession && root.fileSession.hasCurrentFile
                onClicked: root.fileSession.clearCurrentFile()
            }
        }
    }

    component FileActionButton: Button {
        implicitWidth: 138
        implicitHeight: 30
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
        contentItem: Text {
            text: parent.text
            color: parent.enabled ? root.theme.textPrimary : root.theme.muted
            font: parent.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
        background: Rectangle {
            color: parent.enabled
                ? root.theme.surface
                : Qt.rgba(root.theme.muted.r, root.theme.muted.g, root.theme.muted.b, 0.08)
            border.color: parent.enabled
                ? root.theme.border
                : Qt.rgba(root.theme.border.r, root.theme.border.g, root.theme.border.b, 0.5)
            radius: root.theme.radiusSmall
        }
    }
}

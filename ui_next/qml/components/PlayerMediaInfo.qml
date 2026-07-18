import QtQuick
import QtQuick.Layouts

import "../theme"

Item {
    id: root
    objectName: "globalPlayerMediaInfo"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false
    property bool narrowMode: false

    implicitWidth: narrowMode ? 180 : 300
    implicitHeight: compactMode ? 30 : 34

    function originLabel(origin) {
        if (origin === "folder_tree")
            return "文件夹树载入"
        if (origin === "transcode_source")
            return "转码源文件"
        if (origin === "transcode_output")
            return "转码输出结果"
        if (origin === "editor_file")
            return "编辑文件"
        if (origin === "pitch_preview")
            return "Pitch 试听"
        if (origin === "editor_export")
            return "编辑导出结果"
        if (origin === "none")
            return "未加载"
        return "未知来源"
    }

    function editorRelationLabel() {
        if (!root.audioPlayer
                || !root.audioPlayer.hasPlaybackSource
                || !root.audioPlayer.currentFilePath)
            return ""
        return root.audioPlayer.playbackMatchesEditorFile
            ? " · 与编辑文件一致"
            : " · 与编辑文件不同"
    }

    function errorSummary() {
        return root.audioPlayer && root.audioPlayer.error
            ? " · " + root.audioPlayer.error
            : ""
    }

    RowLayout {
        anchors.fill: parent
        spacing: root.theme.spacingSm

        Rectangle {
            Layout.preferredWidth: root.compactMode ? 28 : 32
            Layout.preferredHeight: width
            color: root.theme.panelBackgroundRaised
            border.color: root.theme.borderNormal
            border.width: 1
            radius: root.theme.radiusSmall

            Text {
                anchors.centerIn: parent
                text: "♪"
                color: root.theme.textSecondary
                font.family: root.typography.fontFamily
                font.pixelSize: root.compactMode
                    ? root.typography.sizeMedium
                    : root.typography.sizeLarge
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 0

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.audioPlayer && root.audioPlayer.hasPlaybackSource
                    ? root.audioPlayer.currentPlaybackFileName
                    : "未载入播放文件"
                color: root.theme.textPrimary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                font.weight: root.typography.weightMedium
                elide: Text.ElideMiddle
                maximumLineCount: 1
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.originLabel(
                    root.audioPlayer ? root.audioPlayer.playbackOrigin : "none"
                ) + root.editorRelationLabel() + root.errorSummary()
                color: root.audioPlayer && root.audioPlayer.error
                    ? root.theme.error
                    : root.audioPlayer
                        && root.audioPlayer.hasPlaybackSource
                        && root.audioPlayer.currentFilePath
                        && !root.audioPlayer.playbackMatchesEditorFile
                        ? root.theme.warning
                        : root.theme.textSecondary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeTiny
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }
}

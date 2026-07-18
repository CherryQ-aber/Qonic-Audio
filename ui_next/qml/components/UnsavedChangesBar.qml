import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property bool metadataDirty: false
    property bool coverDirty: false
    property bool lyricsDirty: false
    property string statusMessage: ""

    function dirtySummary() {
        var parts = []
        if (metadataDirty) {
            parts.push("音频信息")
        }
        if (coverDirty) {
            parts.push("封面")
        }
        if (lyricsDirty) {
            parts.push("歌词")
        }
        if (parts.length === 0) {
            return "当前文件信息已同步"
        }
        return "未写入修改：" + parts.join("、")
    }

    implicitHeight: 42
    color: metadataDirty || coverDirty || lyricsDirty
           ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.15)
           : Qt.rgba(theme.success.r, theme.success.g, theme.success.b, 0.12)
    border.color: metadataDirty || coverDirty || lyricsDirty ? theme.warning : theme.success
    border.width: 1
    radius: theme.radiusSmall

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing
        anchors.rightMargin: theme.spacing
        spacing: theme.spacing

        Text {
            text: root.dirtySummary()
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeBody
            font.weight: typography.weightMedium
            Layout.preferredWidth: 220
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 20
            color: theme.border
        }

        Text {
            text: root.statusMessage
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel: null

    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacing + 4
        spacing: theme.spacing

        Text {
            text: "歌词正文只读预览"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeMedium
            font.weight: typography.weightBold
            Layout.fillWidth: true
        }

        TextArea {
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: root.viewModel ? root.viewModel.lyricsText : ""
            readOnly: true
            selectByMouse: true
            color: theme.textPrimary
            selectedTextColor: theme.textInverse
            selectionColor: theme.selectedIndicator
            wrapMode: TextEdit.Wrap
            font.family: "Consolas"
            font.pixelSize: typography.sizeBody
            placeholderText: "当前没有可预览歌词。"
            placeholderTextColor: theme.textMuted
            background: Rectangle {
                color: theme.inputBackground
                border.color: parent.activeFocus ? theme.focusRing : theme.borderNormal
                border.width: parent.activeFocus ? 2 : 1
                radius: theme.radiusSmall
            }
        }

        Text {
            text: "只允许选择和复制文本；编辑与播放器同步均未接入。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}

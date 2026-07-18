import QtQuick
import QtQuick.Layouts

import "../theme"

ColumnLayout {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string title: "暂无内容"
    property string detail: "当前没有可显示的数据。"

    spacing: theme.spacingXs

    ActionIcon {
        theme: root.theme
        typography: root.typography
        name: "details"
        enabledState: false
        Layout.alignment: Qt.AlignHCenter
    }

    Text {
        text: root.title
        color: theme.textSecondary
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeBody
        font.weight: typography.weightMedium
        Layout.alignment: Qt.AlignHCenter
    }

    Text {
        text: root.detail
        color: theme.textMuted
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        Layout.alignment: Qt.AlignHCenter
    }
}

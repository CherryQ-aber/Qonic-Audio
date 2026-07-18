import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}

    implicitHeight: 96
    color: theme.panel
    border.color: theme.border
    border.width: 1
    radius: theme.radiusSmall
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: 7

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "波形功能暂缓"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: "纯占位"
                tone: "muted"
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: theme.surface
            border.color: theme.border
            radius: theme.radiusSmall

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                height: 1
                color: theme.muted
            }

            Text {
                anchors.centerIn: parent
                text: "不读取音频数据 · 不生成 peak 缓存"
                color: theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
            }
        }
    }
}

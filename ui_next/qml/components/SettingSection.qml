import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string title: ""
    property string subtitle: ""
    property string tone: "normal"
    property string statusLabel: ""
    property string statusTone: "muted"
    default property alias content: contentColumn.data

    Layout.fillWidth: true
    implicitHeight: contentRoot.implicitHeight + theme.spacing * 2
    color: theme.panel
    border.color: tone === "danger" ? theme.danger : tone === "warning" ? theme.warning : theme.border
    border.width: tone === "normal" ? 1 : 2
    radius: theme.radiusMedium

    ColumnLayout {
        id: contentRoot
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: theme.spacing + 4
        spacing: theme.spacing

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: root.title
                    color: theme.textPrimary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeMedium
                    font.weight: typography.weightBold
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                StatusBadge {
                    visible: root.statusLabel.length > 0
                    theme: root.theme
                    typography: root.typography
                    label: root.statusLabel
                    tone: root.statusTone
                }
            }

            Text {
                visible: root.subtitle.length > 0
                text: root.subtitle
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                maximumLineCount: 2
            }
        }

        ColumnLayout {
            id: contentColumn
            Layout.fillWidth: true
            spacing: 10
        }
    }
}

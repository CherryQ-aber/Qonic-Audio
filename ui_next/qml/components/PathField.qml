import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string label: ""
    property string path: ""
    property string helperText: ""
    property bool browseEnabled: true
    property bool draftOnly: false
    property string tone: "normal"

    signal browseRequested()

    Layout.fillWidth: true
    implicitHeight: pathContent.implicitHeight + 20
    color: theme.surface
    border.color: tone === "warning" ? theme.warning : tone === "danger" ? theme.danger : theme.border
    border.width: tone === "normal" ? 1 : 2
    radius: theme.radiusSmall

    ColumnLayout {
        id: pathContent
        anchors.fill: parent
        anchors.margins: 10
        spacing: 5

        GridLayout {
            id: pathGrid

            Layout.fillWidth: true
            Layout.minimumWidth: 0
            columns: root.width >= 620 ? 3 : 1
            rowSpacing: 10
            columnSpacing: 10

            Text {
                text: root.label
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeBody
                font.weight: typography.weightMedium
                Layout.preferredWidth: pathGrid.columns === 3 ? 124 : -1
                Layout.fillWidth: pathGrid.columns === 1
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Rectangle {
                Layout.minimumWidth: 0
                Layout.fillWidth: true
                implicitHeight: 28
                color: Qt.rgba(0, 0, 0, 0.16)
                border.color: theme.border
                radius: theme.radiusSmall

                Text {
                    id: pathText
                    anchors.fill: parent
                    anchors.leftMargin: 9
                    anchors.rightMargin: 9
                    verticalAlignment: Text.AlignVCenter
                    text: root.path.length > 0 ? root.path : "-"
                    color: root.path.length > 0 ? theme.textSecondary : theme.muted
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    elide: Text.ElideMiddle
                    maximumLineCount: 1

                    ToolTip.visible: pathMouse.containsMouse && root.path.length > 0
                    ToolTip.text: root.path

                    MouseArea {
                        id: pathMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }
                }
            }

            Rectangle {
                visible: root.browseEnabled
                Layout.preferredWidth: 72
                Layout.minimumWidth: 72
                implicitHeight: 28
                color: browseMouse.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.20) : Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.12)
                border.color: theme.accent
                radius: theme.radiusSmall

                Text {
                    anchors.centerIn: parent
                    text: root.draftOnly ? "选择草稿" : "选择"
                    color: theme.textPrimary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    font.weight: typography.weightMedium
                }

                MouseArea {
                    id: browseMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.browseRequested()
                }
            }
        }

        Text {
            visible: root.helperText.length > 0
            text: root.helperText
            color: tone === "danger" ? theme.danger : tone === "warning" ? theme.warning : theme.muted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTiny
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
    }
}

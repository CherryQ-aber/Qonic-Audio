import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string statusText: "就绪"
    property string logSummary: "暂无日志"

    signal openLogRequested()

    function focusLogButton() {
        logButton.forceActiveFocus()
    }

    implicitHeight: 34
    color: theme.panel
    border.color: theme.border
    border.width: 1

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing + 4
        anchors.rightMargin: theme.spacing + 4
        spacing: theme.spacing

        Text {
            text: root.statusText
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.preferredWidth: 220
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 18
            color: theme.border
        }

        Item {
            Layout.fillWidth: true
        }

        Text {
            text: root.logSummary
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.maximumWidth: 420
            elide: Text.ElideRight
            maximumLineCount: 1
            horizontalAlignment: Text.AlignRight
        }

        WorkstationButton {
            id: logButton
            objectName: "openLogButton"

            Layout.preferredWidth: 86
            Accessible.description: "打开内存日志抽屉"
            theme: root.theme
            typography: root.typography
            tone: "ghost"
            iconName: "log"
            text: "日志"
            onClicked: root.openLogRequested()
        }
    }
}

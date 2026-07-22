import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../pages"
import "../theme"

Popup {
    id: root
    objectName: "settingsOverlay"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property bool openRequested: false
    property bool componentReady: false

    signal closeRequested()

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1180, parent ? parent.width - theme.spacing * 4 : 1180)
    height: Math.min(860, parent ? parent.height - theme.spacing * 4 : 860)
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape

    function synchronizeOpenState() {
        if (!componentReady)
            return
        if (openRequested && !opened)
            open()
        else if (!openRequested && opened)
            close()
    }

    onOpenRequestedChanged: synchronizeOpenState()
    onOpened: {
        closeButton.forceActiveFocus()
        settingsViewModel.refreshStorageUsage()
    }
    onClosed: {
        if (openRequested)
            closeRequested()
    }
    Component.onCompleted: {
        componentReady = true
        synchronizeOpenState()
    }

    background: Rectangle {
        color: theme.panel
        border.color: theme.border
        border.width: 1
        radius: theme.radiusMedium
    }

    contentItem: ColumnLayout {
        enabled: root.opened
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 48
            color: root.theme.panel
            border.color: root.theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.theme.spacing
                anchors.rightMargin: root.theme.spacing
                spacing: root.theme.spacing

                Text {
                    text: "全局设置"
                    color: root.theme.textPrimary
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeMedium
                    font.weight: root.typography.weightBold
                    Layout.fillWidth: true
                }

                WorkstationButton {
                    id: closeButton
                    objectName: "closeSettingsOverlayButton"
                    Layout.preferredWidth: 86
                    theme: root.theme
                    typography: root.typography
                    text: "关闭"
                    iconName: "close"
                    tone: "ghost"
                    onClicked: root.closeRequested()
                }
            }
        }

        SettingsPage {
            id: settingsPage
            objectName: "settingsOverlayPage"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            theme: root.theme
            typography: root.typography
        }
    }
}

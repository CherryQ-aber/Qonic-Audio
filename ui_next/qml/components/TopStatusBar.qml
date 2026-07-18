import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "globalTopBar"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string appName: "CherryQ Audio Converter"
    property string moduleName: ""
    property string statusSummary: ""
    property string modeLabel: "预览模式"
    property string capabilityLabel: ""
    property string versionLabel: ""
    property var workspaces: []
    property string currentWorkspaceKey: "autoConvert"

    signal workspaceRequested(string workspaceKey)
    signal settingsRequested()
    signal logRequested()

    function focusSettingsButton() {
        settingsButton.forceActiveFocus()
    }

    function focusLogButton() {
        globalLogButton.forceActiveFocus()
    }

    function focusCurrentWorkspace() {
        workspaceSwitcher.focusCurrentItem()
    }

    implicitHeight: 58
    color: theme.panel
    border.color: theme.border
    border.width: 1

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing + 4
        anchors.rightMargin: theme.spacing + 4
        spacing: theme.spacing

        ColumnLayout {
            Layout.preferredWidth: 210
            Layout.minimumWidth: 150
            spacing: 2

            Text {
                text: root.appName
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
            }

            Text {
                text: root.moduleName
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
            }
        }

        WorkspaceSwitcher {
            id: workspaceSwitcher
            theme: root.theme
            typography: root.typography
            workspaces: root.workspaces
            currentWorkspaceKey: root.currentWorkspaceKey
            onWorkspaceRequested: function(workspaceKey) {
                root.workspaceRequested(workspaceKey)
            }
        }

        Item {
            Layout.fillWidth: true
        }

        StatusBadge {
            objectName: "modeStatusBadge"
            visible: root.modeLabel.length > 0
            theme: root.theme
            typography: root.typography
            label: root.modeLabel
            tone: root.modeLabel === "预览模式" ? "muted" : "accent"
        }

        StatusBadge {
            objectName: "capabilityStatusBadge"
            visible: root.width >= 1360
                && root.capabilityLabel.length > 0
                && root.capabilityLabel !== root.modeLabel
            theme: root.theme
            typography: root.typography
            label: root.capabilityLabel
            tone: root.capabilityLabel === "预览模式" ? "muted" : "accent"
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 26
            color: theme.border
        }

        WorkstationButton {
            id: settingsButton
            objectName: "openSettingsButton"
            Layout.preferredWidth: 86
            theme: root.theme
            typography: root.typography
            text: "设置"
            tone: "ghost"
            toolTipText: "打开全局设置；不会切换当前工作区"
            onClicked: root.settingsRequested()
        }

        WorkstationButton {
            id: globalLogButton
            objectName: "openGlobalLogButton"
            Layout.preferredWidth: 78
            theme: root.theme
            typography: root.typography
            text: "日志"
            iconName: "log"
            tone: "ghost"
            toolTipText: "打开全局内存日志"
            onClicked: root.logRequested()
        }

        Text {
            text: root.versionLabel
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            horizontalAlignment: Text.AlignRight
        }
    }
}

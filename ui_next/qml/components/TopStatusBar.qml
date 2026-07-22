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
    property string versionLabel: ""
    property var workspaces: []
    property string currentWorkspaceKey: "autoConvert"
    property bool autoConvertActive: false
    property string autoConvertStatusText: ""
    property bool editorHasUnsavedDrafts: false
    property bool folderBrowserAvailable: false
    property bool folderPaneVisible: false

    signal workspaceRequested(string workspaceKey)
    signal folderPaneToggleRequested()
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
            Layout.maximumWidth: 210
            Layout.fillWidth: false
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
            autoConvertActive: root.autoConvertActive
            autoConvertStatusText: root.autoConvertStatusText
            editorHasUnsavedDrafts: root.editorHasUnsavedDrafts
            onWorkspaceRequested: function(workspaceKey) {
                root.workspaceRequested(workspaceKey)
            }
        }

        Item {
            Layout.fillWidth: true
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 26
            color: theme.divider
        }

        WorkstationButton {
            id: folderBrowserButton
            objectName: "toggleGlobalFolderBrowserButton"
            visible: root.folderBrowserAvailable
            Layout.preferredWidth: 72
            theme: root.theme
            typography: root.typography
            text: "文件"
            iconName: "folder"
            tone: root.folderPaneVisible ? "secondary" : "ghost"
            toolTipText: root.folderPaneVisible
                ? "收起全局文件浏览栏"
                : "展开全局文件浏览栏"
            onClicked: root.folderPaneToggleRequested()
        }

        WorkstationButton {
            id: settingsButton
            objectName: "openSettingsButton"
            Layout.preferredWidth: 76
            theme: root.theme
            typography: root.typography
            text: "设置"
            iconName: "settings"
            tone: "ghost"
            borderless: true
            toolTipText: "打开全局设置；不会切换当前工作区"
            onClicked: root.settingsRequested()
        }

        WorkstationButton {
            id: globalLogButton
            objectName: "openGlobalLogButton"
            Layout.preferredWidth: 72
            theme: root.theme
            typography: root.typography
            text: "日志"
            iconName: "log"
            tone: "ghost"
            borderless: true
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

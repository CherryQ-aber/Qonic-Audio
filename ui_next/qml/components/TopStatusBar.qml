import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "globalTopBar"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string appName: "Qonic Audio"
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
    property bool navigationEnabled: true
    property bool nativeWindowChrome: false
    property bool windowActive: true
    property bool windowMaximized: false
    property var windowController: null
    property url applicationIconSource: ""

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

    function scheduleNativeHitTestSync() {
        if (!root.nativeWindowChrome || !root.windowController)
            return
        hitTestSyncTimer.restart()
    }

    function mappedRect(item) {
        if (!item || !item.visible || item.width <= 0 || item.height <= 0)
            return null
        var point = item.mapToItem(root, 0, 0)
        return {
            "x": point.x,
            "y": point.y,
            "width": item.width,
            "height": item.height
        }
    }

    function syncNativeHitTestRegions() {
        if (!root.nativeWindowChrome || !root.windowController)
            return
        root.windowController.setCaptionRects([
            {
                "x": 0,
                "y": 0,
                "width": root.width,
                "height": root.height
            }
        ])
        var interactiveRects = []
        var interactiveItems = [
            workspaceSwitcher,
            folderBrowserButton,
            settingsButton,
            globalLogButton
        ]
        for (var index = 0; index < interactiveItems.length; index += 1) {
            var rect = root.mappedRect(interactiveItems[index])
            if (rect)
                interactiveRects.push(rect)
        }
        root.windowController.setInteractiveRects(interactiveRects)
        windowControls.registerNativeHitRects(root)
    }

    Timer {
        id: hitTestSyncTimer
        interval: 0
        repeat: false
        onTriggered: root.syncNativeHitTestRegions()
    }

    implicitHeight: 58
    color: theme.panel
    border.color: theme.border
    border.width: 1

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing
        anchors.rightMargin: root.nativeWindowChrome ? 0 : theme.spacing
        spacing: theme.spacingSm

        Item {
            id: brandPanel
            objectName: "applicationBrandRegion"
            Layout.preferredWidth: 224
            Layout.minimumWidth: 190
            Layout.maximumWidth: 224
            Layout.fillHeight: true
            Layout.fillWidth: false

            Image {
                id: applicationIcon
                objectName: "applicationTitleIcon"
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: 22
                height: 22
                source: root.applicationIconSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
                visible: source.toString().length > 0
            }

            Column {
                anchors.left: applicationIcon.visible
                    ? applicationIcon.right : parent.left
                anchors.leftMargin: applicationIcon.visible ? theme.spacingSm : 0
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    width: parent.width
                    text: root.appName
                    color: root.windowActive
                        ? theme.textPrimary : theme.titleBarInactiveText
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeMedium
                    font.weight: typography.weightBold
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Text {
                    width: parent.width
                    text: root.moduleName
                    color: root.windowActive
                        ? theme.textSecondary : theme.titleBarInactiveText
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
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
            enabled: root.navigationEnabled
            onWorkspaceRequested: function(workspaceKey) {
                root.workspaceRequested(workspaceKey)
            }
            onXChanged: root.scheduleNativeHitTestSync()
            onYChanged: root.scheduleNativeHitTestSync()
            onWidthChanged: root.scheduleNativeHitTestSync()
            onHeightChanged: root.scheduleNativeHitTestSync()
        }

        Item {
            id: titleDragRegion
            objectName: "windowTitleDragRegion"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0

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
            enabled: root.navigationEnabled
            onClicked: root.folderPaneToggleRequested()
            onXChanged: root.scheduleNativeHitTestSync()
            onYChanged: root.scheduleNativeHitTestSync()
            onWidthChanged: root.scheduleNativeHitTestSync()
            onHeightChanged: root.scheduleNativeHitTestSync()
            onVisibleChanged: root.scheduleNativeHitTestSync()
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
            enabled: root.navigationEnabled
            onClicked: root.settingsRequested()
            onXChanged: root.scheduleNativeHitTestSync()
            onYChanged: root.scheduleNativeHitTestSync()
            onWidthChanged: root.scheduleNativeHitTestSync()
            onHeightChanged: root.scheduleNativeHitTestSync()
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
            enabled: root.navigationEnabled
            onClicked: root.logRequested()
            onXChanged: root.scheduleNativeHitTestSync()
            onYChanged: root.scheduleNativeHitTestSync()
            onWidthChanged: root.scheduleNativeHitTestSync()
            onHeightChanged: root.scheduleNativeHitTestSync()
        }

        Text {
            Layout.preferredWidth: 112
            Layout.maximumWidth: 112
            text: root.versionLabel
            color: root.windowActive
                ? theme.textSecondary : theme.titleBarInactiveText
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Rectangle {
            visible: root.nativeWindowChrome
            Layout.preferredWidth: 1
            Layout.preferredHeight: 26
            color: theme.divider
        }

        WindowControls {
            id: windowControls
            visible: root.nativeWindowChrome
            Layout.preferredWidth: visible ? implicitWidth : 0
            Layout.minimumWidth: visible ? implicitWidth : 0
            Layout.maximumWidth: visible ? implicitWidth : 0
            Layout.fillHeight: true
            // Preserve a real top-right resize strip without creating a
            // visually significant gap after the close button.
            Layout.rightMargin: visible ? 7 : 0
            theme: root.theme
            typography: root.typography
            windowController: root.windowController
            windowActive: root.windowActive
            windowMaximized: root.windowMaximized
            onGeometryChanged: root.scheduleNativeHitTestSync()
        }
    }

    onWidthChanged: scheduleNativeHitTestSync()
    onHeightChanged: scheduleNativeHitTestSync()
    onNativeWindowChromeChanged: scheduleNativeHitTestSync()
    onWindowControllerChanged: scheduleNativeHitTestSync()
    Component.onCompleted: scheduleNativeHitTestSync()
}

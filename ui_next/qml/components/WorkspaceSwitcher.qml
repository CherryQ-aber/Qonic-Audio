import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

RowLayout {
    id: root
    objectName: "workspaceSwitcher"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var workspaces: []
    property string currentWorkspaceKey: "autoConvert"
    property int tabStopIndex: currentWorkspaceIndex()

    signal workspaceRequested(string workspaceKey)

    spacing: theme.spacingSm

    function currentWorkspaceIndex() {
        for (var index = 0; index < workspaces.length; index += 1) {
            if (workspaces[index].key === currentWorkspaceKey)
                return index
        }
        return 0
    }

    function focusIndex(targetIndex) {
        if (workspaceRepeater.count === 0)
            return
        var boundedIndex = Math.max(
            0,
            Math.min(targetIndex, workspaceRepeater.count - 1)
        )
        var item = workspaceRepeater.itemAt(boundedIndex)
        if (item) {
            tabStopIndex = boundedIndex
            item.forceActiveFocus()
        }
    }

    function focusCurrentItem() {
        focusIndex(currentWorkspaceIndex())
    }

    function activateIndex(targetIndex) {
        var item = workspaceRepeater.itemAt(targetIndex)
        if (!item || !item.enabled)
            return
        tabStopIndex = targetIndex
        root.workspaceRequested(item.workspaceKey)
        item.forceActiveFocus()
    }

    onCurrentWorkspaceKeyChanged: tabStopIndex = currentWorkspaceIndex()

    Repeater {
        id: workspaceRepeater
        model: root.workspaces

        delegate: WorkstationButton {
            required property int index
            required property var modelData

            property string workspaceKey: modelData.key
            property bool selected: workspaceKey === root.currentWorkspaceKey

            objectName: "workspaceSwitch_" + workspaceKey
            Layout.preferredWidth: 126
            implicitHeight: root.theme.controlHeightLarge
            theme: root.theme
            typography: root.typography
            text: modelData.title
            tone: selected ? "primary" : "ghost"
            activeFocusOnTab: root.tabStopIndex === index
            Accessible.checked: selected
            Accessible.description: selected
                ? "当前一级工作区：" + modelData.title
                : "切换到一级工作区：" + modelData.title

            onActiveFocusChanged: {
                if (activeFocus)
                    root.tabStopIndex = index
            }
            onClicked: root.activateIndex(index)

            Keys.priority: Keys.BeforeItem
            Keys.onLeftPressed: function(event) {
                root.focusIndex(index - 1)
                event.accepted = true
            }
            Keys.onRightPressed: function(event) {
                root.focusIndex(index + 1)
                event.accepted = true
            }
            Keys.onReturnPressed: function(event) {
                root.activateIndex(index)
                event.accepted = true
            }
            Keys.onEnterPressed: function(event) {
                root.activateIndex(index)
                event.accepted = true
            }
            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Home) {
                    root.focusIndex(0)
                    event.accepted = true
                } else if (event.key === Qt.Key_End) {
                    root.focusIndex(workspaceRepeater.count - 1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Space) {
                    root.activateIndex(index)
                    event.accepted = true
                }
            }
        }
    }
}

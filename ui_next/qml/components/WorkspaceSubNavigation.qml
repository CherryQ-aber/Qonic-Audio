import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "workspaceSubNavigation"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string currentWorkspaceKey: "autoConvert"
    property string currentEditorPageKey: "fileInfo"
    property var editorPages: []
    property int tabStopIndex: currentPageIndex()
    readonly property var currentModel: currentWorkspaceKey === "audioEditor"
        ? editorPages
        : [{"key": "all", "title": "全部任务"}]

    signal editorPageRequested(string pageKey)

    implicitHeight: 44
    color: theme.panel
    border.color: theme.border
    border.width: 1

    function selectedKey() {
        return currentWorkspaceKey === "audioEditor"
            ? currentEditorPageKey
            : "all"
    }

    function currentPageIndex() {
        var key = selectedKey()
        for (var index = 0; index < currentModel.length; index += 1) {
            if (currentModel[index].key === key)
                return index
        }
        return 0
    }

    function focusIndex(targetIndex) {
        if (subNavigationRepeater.count === 0)
            return
        var boundedIndex = Math.max(
            0,
            Math.min(targetIndex, subNavigationRepeater.count - 1)
        )
        var item = subNavigationRepeater.itemAt(boundedIndex)
        if (item) {
            tabStopIndex = boundedIndex
            item.forceActiveFocus()
        }
    }

    function focusCurrentItem() {
        focusIndex(currentPageIndex())
    }

    function activateIndex(targetIndex) {
        var item = subNavigationRepeater.itemAt(targetIndex)
        if (!item || !item.enabled)
            return
        tabStopIndex = targetIndex
        if (root.currentWorkspaceKey === "audioEditor")
            root.editorPageRequested(item.pageKey)
        item.forceActiveFocus()
    }

    onCurrentWorkspaceKeyChanged: tabStopIndex = currentPageIndex()
    onCurrentEditorPageKeyChanged: tabStopIndex = currentPageIndex()

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing + 4
        anchors.rightMargin: theme.spacing + 4
        spacing: theme.spacingSm

        Text {
            text: root.currentWorkspaceKey === "audioEditor"
                ? "编辑页面"
                : "任务视图"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightMedium
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 22
            color: theme.border
        }

        Repeater {
            id: subNavigationRepeater
            model: root.currentModel

            delegate: WorkstationButton {
                required property int index
                required property var modelData

                property string pageKey: modelData.key
                property bool selected: pageKey === root.selectedKey()

                objectName: "workspaceSubNav_" + pageKey
                Layout.preferredWidth: root.currentWorkspaceKey === "audioEditor"
                    ? 116 : 104
                implicitHeight: root.theme.controlHeightSmall
                theme: root.theme
                typography: root.typography
                text: modelData.title
                tone: selected ? "primary" : "ghost"
                activeFocusOnTab: root.tabStopIndex === index
                Accessible.checked: selected
                Accessible.description: selected
                    ? "当前二级页面：" + modelData.title
                    : "切换到二级页面：" + modelData.title

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
                        root.focusIndex(subNavigationRepeater.count - 1)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Space) {
                        root.activateIndex(index)
                        event.accepted = true
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
        }
    }
}

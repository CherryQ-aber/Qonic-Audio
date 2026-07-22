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
    property var taskQueueModel: null
    property string taskFilterKey: "all"
    property bool editorFileBarFloating: false
    property bool editorFileBarExpanded: false
    property int tabStopIndex: currentPageIndex()
    readonly property int totalTaskCount: taskQueueModel
        ? Number(taskQueueModel.totalCount)
        : 0
    readonly property int waitingTaskCount: taskQueueModel
        ? Number(taskQueueModel.waitingCount)
        : 0
    readonly property int processingTaskCount: taskQueueModel
        ? Number(taskQueueModel.processingCount)
        : 0
    readonly property int excludedTaskCount: taskQueueModel
        ? Number(taskQueueModel.excludedCount)
        : 0
    readonly property int completedTaskCount: taskQueueModel
        ? Number(taskQueueModel.completedCount)
        : 0
    readonly property int failedTaskCount: taskQueueModel
        ? Number(taskQueueModel.failedCount)
        : 0
    readonly property var autoConvertFilters: [
        {
            "key": "all",
            "title": "全部",
            "preferredWidth": 96
        },
        {
            "key": "waiting",
            "title": "等待处理",
            "preferredWidth": 116
        },
        {
            "key": "processing",
            "title": "处理中",
            "preferredWidth": 104
        },
        {
            "key": "excluded",
            "title": "本轮跳过",
            "preferredWidth": 116
        },
        {
            "key": "completed",
            "title": "已完成",
            "preferredWidth": 104
        },
        {
            "key": "failed",
            "title": "失败",
            "preferredWidth": 92
        }
    ]
    readonly property var currentModel: currentWorkspaceKey === "audioEditor"
        ? editorPages
        : autoConvertFilters

    signal editorPageRequested(string pageKey)
    signal taskFilterRequested(string filterKey)
    signal editorFileBarToggleRequested()

    implicitHeight: 44
    color: theme.panel
    border.color: theme.border
    border.width: 1

    function selectedKey() {
        return currentWorkspaceKey === "audioEditor"
            ? currentEditorPageKey
            : taskFilterKey
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
        else
            root.taskFilterRequested(item.pageKey)
        item.forceActiveFocus()
    }

    onCurrentWorkspaceKeyChanged: tabStopIndex = currentPageIndex()
    onCurrentEditorPageKeyChanged: tabStopIndex = currentPageIndex()
    onTaskFilterKeyChanged: tabStopIndex = currentPageIndex()

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing + 4
        anchors.rightMargin: theme.spacing + 4
        spacing: theme.spacingSm

        Text {
            text: root.currentWorkspaceKey === "audioEditor"
                ? "音频编辑"
                : "自动转码"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightMedium
        }

        Text {
            text: "/"
            color: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
        }

        Repeater {
            id: subNavigationRepeater
            model: root.currentModel

            delegate: WorkstationButton {
                required property int index
                required property var modelData

                property string pageKey: modelData.key
                property bool selected: pageKey === root.selectedKey()
                property int taskCount: pageKey === "all"
                    ? root.totalTaskCount
                    : pageKey === "waiting"
                        ? root.waitingTaskCount
                        : pageKey === "processing"
                            ? root.processingTaskCount
                            : pageKey === "excluded"
                                ? root.excludedTaskCount
                                : pageKey === "completed"
                                    ? root.completedTaskCount
                                    : pageKey === "failed"
                                        ? root.failedTaskCount
                                        : 0
                property string navigationTitle:
                    root.currentWorkspaceKey === "audioEditor"
                    ? modelData.title
                    : modelData.title + " " + taskCount

                objectName: "workspaceSubNav_" + pageKey
                Layout.preferredWidth: root.currentWorkspaceKey === "audioEditor"
                    ? 116 : modelData.preferredWidth
                implicitHeight: root.theme.controlHeightSmall
                theme: root.theme
                typography: root.typography
                text: navigationTitle
                tone: "ghost"
                selectedState: selected
                borderless: true
                activeFocusOnTab: root.tabStopIndex === index
                Accessible.checked: selected
                Accessible.description: selected
                    ? "当前二级页面：" + navigationTitle
                    : "切换到二级页面：" + navigationTitle

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

        WorkstationButton {
            id: editorFileBarToggleButton
            objectName: "toggleEditorFileBarButton"
            visible: root.currentWorkspaceKey === "audioEditor"
                && root.editorFileBarFloating
            Layout.preferredWidth: 142
            implicitHeight: root.theme.controlHeightSmall
            theme: root.theme
            typography: root.typography
            text: root.editorFileBarExpanded ? "收起公共文件栏" : "展开公共文件栏"
            tone: root.editorFileBarExpanded ? "primary" : "ghost"
            toolTipText: root.editorFileBarExpanded
                ? "收起顶部公共文件栏，恢复完整编辑视图。"
                : "从顶部展开当前编辑文件与公共操作。"
            onClicked: root.editorFileBarToggleRequested()
        }
    }
}

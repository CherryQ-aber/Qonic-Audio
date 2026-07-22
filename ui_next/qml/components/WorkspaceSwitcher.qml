import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "workspaceSwitcher"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var workspaces: []
    property string currentWorkspaceKey: "autoConvert"
    property bool autoConvertActive: false
    property string autoConvertStatusText: ""
    property bool editorHasUnsavedDrafts: false
    property int tabStopIndex: currentWorkspaceIndex()
    readonly property color activeBackground: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.12 : 0.16
    )
    readonly property color activeHoverBackground: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.18 : 0.22
    )
    readonly property color inactiveHoverBackground: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.08 : 0.10
    )
    readonly property color pressedBackground: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.24 : 0.28
    )

    signal workspaceRequested(string workspaceKey)

    implicitWidth: workspaceRow.implicitWidth + 4
    implicitHeight: theme.controlHeightLarge
    color: theme.inputBackground
    border.color: theme.borderSubtle
    border.width: 1
    radius: 4

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

    RowLayout {
        id: workspaceRow
        anchors.fill: parent
        anchors.margins: 2
        spacing: 0

        Repeater {
            id: workspaceRepeater
            model: root.workspaces

            delegate: Button {
                required property int index
                required property var modelData

                property string workspaceKey: modelData.key
                property bool selected:
                    workspaceKey === root.currentWorkspaceKey
                property bool showsStatus:
                    workspaceKey === "autoConvert"
                    ? root.autoConvertActive
                    : root.editorHasUnsavedDrafts
                property string statusDescription:
                    workspaceKey === "autoConvert"
                    ? (root.autoConvertStatusText.length > 0
                        ? root.autoConvertStatusText
                        : "监听或任务处理中")
                    : "存在未导出的编辑草稿"

                objectName: "workspaceSwitch_" + workspaceKey
                Layout.preferredWidth: 126
                Layout.fillHeight: true
                implicitHeight: root.implicitHeight - 4
                text: modelData.title
                hoverEnabled: true
                activeFocusOnTab: root.tabStopIndex === index
                focusPolicy: Qt.TabFocus
                Accessible.role: Accessible.PageTab
                Accessible.name: modelData.title
                Accessible.checked: selected
                Accessible.description: (
                    selected
                    ? "当前一级工作区：" + modelData.title
                    : "切换到一级工作区：" + modelData.title
                ) + (showsStatus ? "；" + statusDescription : "")

                contentItem: Row {
                    spacing: root.theme.spacingSm
                    anchors.centerIn: parent

                    ActionIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        theme: root.theme
                        typography: root.typography
                        name: workspaceKey === "autoConvert"
                            ? "refresh" : "editor"
                        tone: selected ? "accent" : "normal"
                        iconSize: root.theme.iconSizeLarge
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.title
                        color: selected
                            ? root.theme.textPrimary
                            : root.theme.textSecondary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        font.weight: selected
                            ? root.typography.weightBold
                            : root.typography.weightMedium
                    }

                    Item {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 6
                        height: 6

                        Rectangle {
                            anchors.fill: parent
                            radius: 3
                            opacity: showsStatus ? 1 : 0
                            color: workspaceKey === "autoConvert"
                                ? root.theme.success
                                : root.theme.warning

                            Behavior on opacity {
                                NumberAnimation {
                                    duration: root.theme.durationFast
                                }
                            }
                        }
                    }
                }

                background: Rectangle {
                    color: !parent.enabled
                        ? root.theme.disabledBackground
                        : parent.pressed
                            ? root.pressedBackground
                            : parent.selected && parent.hovered
                                ? root.activeHoverBackground
                                : parent.selected
                                    ? root.activeBackground
                                    : parent.hovered
                                        ? root.inactiveHoverBackground
                                    : "transparent"
                    border.color: parent.visualFocus
                        ? root.theme.focusRing : "transparent"
                    border.width: parent.visualFocus ? 2 : 0
                    radius: root.theme.radiusSmall

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: root.theme.spacingSm
                        anchors.rightMargin: root.theme.spacingSm
                        height: 2
                        radius: 1
                        visible: workspaceKey
                            === root.currentWorkspaceKey
                        color: root.theme.selectedIndicator
                    }

                    Behavior on color {
                        ColorAnimation {
                            duration: root.theme.durationFast
                        }
                    }
                }

                ThemedToolTip {
                    theme: root.theme
                    typography: root.typography
                    visible: parent.hovered && showsStatus
                    text: statusDescription
                }

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
}

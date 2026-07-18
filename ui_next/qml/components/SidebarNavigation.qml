import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "sidebarNavigation"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var modules: []
    property string currentModuleKey: ""
    property int tabStopIndex: 0
    property int keyboardFocusIndex: -1

    signal moduleRequested(string moduleKey)

    function currentModuleIndex() {
        for (var index = 0; index < modules.length; index += 1) {
            if (modules[index].key === currentModuleKey) {
                return index
            }
        }
        return 0
    }

    function focusNavigationIndex(targetIndex) {
        if (navigationRepeater.count === 0) {
            return
        }

        var clampedIndex = Math.max(0, Math.min(targetIndex, navigationRepeater.count - 1))
        var item = navigationRepeater.itemAt(clampedIndex)
        if (item) {
            tabStopIndex = clampedIndex
            keyboardFocusIndex = clampedIndex
            item.forceActiveFocus()
        }
    }

    function activateNavigationIndex(targetIndex) {
        var item = navigationRepeater.itemAt(targetIndex)
        if (!item || !item.enabled) {
            return
        }

        tabStopIndex = targetIndex
        keyboardFocusIndex = targetIndex
        moduleRequested(item.moduleKey)
        item.forceActiveFocus()
    }

    function activateFromPointer(targetIndex) {
        var item = navigationRepeater.itemAt(targetIndex)
        if (!item || !item.enabled) {
            return
        }

        tabStopIndex = targetIndex
        moduleRequested(item.moduleKey)
    }

    onCurrentModuleKeyChanged: tabStopIndex = currentModuleIndex()

    implicitWidth: 218
    color: theme.panel
    border.color: theme.border
    border.width: 1

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: theme.spacing

        Text {
            text: "工作台"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightMedium
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Repeater {
            id: navigationRepeater
            model: root.modules

            delegate: Button {
                id: navItem
                objectName: "sidebarNavItem_" + moduleKey

                required property int index
                required property var modelData
                property int navigationIndex: index
                property string moduleKey: modelData.key
                property bool selected: moduleKey === root.currentModuleKey

                Layout.fillWidth: true
                implicitHeight: 48
                activeFocusOnTab: root.tabStopIndex === navigationIndex
                focusPolicy: Qt.TabFocus
                hoverEnabled: true
                Accessible.role: Accessible.Button
                Accessible.name: modelData.title
                Accessible.description: selected
                    ? "当前页面：" + modelData.title
                    : "切换到页面：" + modelData.title
                Accessible.checked: selected

                onActiveFocusChanged: {
                    if (activeFocus) {
                        root.tabStopIndex = navigationIndex
                        root.keyboardFocusIndex = navigationIndex
                    }
                }

                onClicked: root.activateFromPointer(navigationIndex)

                Keys.priority: Keys.BeforeItem
                Keys.onUpPressed: function(event) {
                    root.focusNavigationIndex(navigationIndex - 1)
                    event.accepted = true
                }
                Keys.onDownPressed: function(event) {
                    root.focusNavigationIndex(navigationIndex + 1)
                    event.accepted = true
                }
                Keys.onReturnPressed: function(event) {
                    root.activateNavigationIndex(navigationIndex)
                    event.accepted = true
                }
                Keys.onEnterPressed: function(event) {
                    root.activateNavigationIndex(navigationIndex)
                    event.accepted = true
                }
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Home) {
                        root.focusNavigationIndex(0)
                        event.accepted = true
                    } else if (event.key === Qt.Key_End) {
                        root.focusNavigationIndex(navigationRepeater.count - 1)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Space) {
                        root.activateNavigationIndex(navigationIndex)
                        event.accepted = true
                    }
                }

                background: Rectangle {
                    radius: theme.radiusSmall
                    color: navItem.selected
                        ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.14)
                        : navItem.hovered
                            ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.06)
                            : "transparent"
                    border.color: navItem.visualFocus
                        ? theme.accent
                        : navItem.selected
                            ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.55)
                            : "transparent"
                    border.width: navItem.visualFocus ? 2 : navItem.selected ? 1 : 0

                    Behavior on color { ColorAnimation { duration: theme.durationFast } }
                    Behavior on border.color { ColorAnimation { duration: theme.durationFast } }
                }

                contentItem: RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 8
                    spacing: 9

                    Rectangle {
                        Layout.preferredWidth: 3
                        Layout.fillHeight: true
                        Layout.topMargin: 10
                        Layout.bottomMargin: 10
                        radius: 1
                        color: navItem.selected ? theme.accent : theme.border
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: modelData.title
                            color: theme.textPrimary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeBody
                            font.weight: navItem.selected
                                ? typography.weightBold
                                : typography.weightMedium
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        Text {
                            text: modelData.description
                            color: theme.textSecondary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeTiny
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillHeight: true
        }
    }
}

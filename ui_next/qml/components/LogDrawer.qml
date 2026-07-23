import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var logModel
    property string globalStatusSummary: ""
    property bool opened: false
    property bool compactLayout: root.width < 1200
    property int workspaceLeftInset: 0
    property int workspaceRightInset: 0
    property int minimumWorkspaceWidth: 620
    property int compactDrawerHeight: Math.min(320, Math.max(220, root.height * 0.38))
    property int mediumDrawerWidth: 400
    property int wideDrawerMaxWidth: 560
    property int sideDrawerLimit: Math.max(
        340,
        root.width - root.workspaceLeftInset - root.minimumWorkspaceWidth
    )

    signal closeRequested()

    Shortcut {
        enabled: root.opened
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        onActivated: root.closeRequested()
    }

    onOpenedChanged: {
        if (opened) {
            drawerPanel.forceActiveFocus()
            Qt.callLater(function() {
                closeButton.forceActiveFocus(Qt.TabFocusReason)
            })
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.opened
        enabled: visible
        color: theme.overlayBackground

        MouseArea {
            anchors.fill: parent
            onClicked: root.closeRequested()
        }
    }

    Rectangle {
        id: drawerPanel
        objectName: "logDrawerPanel"

        width: root.compactLayout
            ? Math.max(0, root.width - root.workspaceLeftInset - root.workspaceRightInset)
            : Math.min(
                root.width >= 1600 ? root.wideDrawerMaxWidth : root.mediumDrawerWidth,
                root.width >= 1600 ? root.width * 0.35 : root.width * 0.32,
                root.sideDrawerLimit
            )
        height: root.compactLayout ? root.compactDrawerHeight : root.height
        x: root.compactLayout
            ? root.workspaceLeftInset
            : root.opened ? root.width - width : root.width
        y: root.compactLayout
            ? root.opened ? root.height - height : root.height
            : 0
        focus: root.opened
        activeFocusOnTab: root.opened
        focusPolicy: Qt.TabFocus
        enabled: root.opened
        color: theme.drawerBackground
        border.color: theme.border
        border.width: 1

        Behavior on x {
            NumberAnimation {
                duration: theme.durationNormal
                easing.type: Easing.OutCubic
            }
        }

        Behavior on y {
            NumberAnimation {
                duration: theme.durationNormal
                easing.type: Easing.OutCubic
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: theme.spacing + 4
            spacing: theme.spacing

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.spacing

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: "QML 内存日志"
                        color: theme.textPrimary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeLarge
                        font.weight: typography.weightBold
                        Layout.fillWidth: true
                    }

                    Text {
                        objectName: "logDrawerGlobalStatusSummary"
                        visible: root.globalStatusSummary.length > 0
                        text: "当前状态：" + root.globalStatusSummary
                        color: theme.textPrimary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        text: root.logModel ? root.logModel.summary : "日志模型未接入"
                        color: theme.textSecondary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }

                DrawerButton {
                    id: closeButton
                    objectName: "closeLogDrawerButton"
                    theme: root.theme
                    typography: root.typography
                    label: "关闭"
                    KeyNavigation.tab: filterRepeater.itemAt(0)
                    KeyNavigation.backtab: clearLogButton
                    onClicked: root.closeRequested()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Repeater {
                    id: filterRepeater

                    model: [
                        {"value": "all", "label": "全部"},
                        {"value": "info", "label": "Info"},
                        {"value": "warning", "label": "Warning"},
                        {"value": "error", "label": "Error"}
                    ]

                    delegate: WorkstationButton {
                        required property int index
                        required property var modelData

                        Layout.preferredWidth: 86
                        implicitHeight: theme.controlHeightSmall
                        theme: root.theme
                        typography: root.typography
                        tone: root.logModel && root.logModel.filterLevel === modelData.value
                            ? "primary" : "ghost"
                        text: modelData.label
                        KeyNavigation.tab: index < filterRepeater.count - 1
                            ? filterRepeater.itemAt(index + 1) : copyAllButton
                        KeyNavigation.backtab: index > 0
                            ? filterRepeater.itemAt(index - 1) : closeButton
                        onClicked: {
                            if (root.logModel) {
                                root.logModel.setFilterLevel(modelData.value)
                            }
                        }
                    }
                }
            }

            ListView {
                id: logList

                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: root.logModel

                ScrollBar.vertical: ThemeScrollBar {
                    theme: root.theme
                }

                delegate: Rectangle {
                    required property string time
                    required property string level
                    required property string message

                    width: logList.width
                    implicitHeight: logRow.implicitHeight + 14
                    color: theme.surface
                    border.color: level === "error" ? theme.danger : level === "warning" ? theme.warning : theme.border
                    radius: theme.radiusSmall

                    RowLayout {
                        id: logRow
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 8
                        spacing: 8

                        Text {
                            text: time
                            color: theme.muted
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeTiny
                            Layout.preferredWidth: 54
                            maximumLineCount: 1
                        }

                        Text {
                            text: level.toUpperCase()
                            color: level === "error" ? theme.danger : level === "warning" ? theme.warning : theme.accent
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeTiny
                            font.weight: typography.weightBold
                            Layout.preferredWidth: 58
                            maximumLineCount: 1
                        }

                        TextEdit {
                            text: message
                            color: theme.textSecondary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            wrapMode: TextEdit.WordWrap
                            textFormat: TextEdit.PlainText
                            readOnly: true
                            selectByMouse: true
                            activeFocusOnTab: false
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: !root.logModel || root.logModel.rowCount() === 0
                    text: "暂无可显示日志"
                    color: theme.muted
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeBody
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                DrawerButton {
                    id: copyAllButton

                    theme: root.theme
                    typography: root.typography
                    label: "复制全部"
                    KeyNavigation.tab: clearLogButton
                    KeyNavigation.backtab: filterRepeater.itemAt(filterRepeater.count - 1)
                    onClicked: {
                        if (root.logModel) {
                            root.logModel.copyAllText()
                        }
                    }
                }

                DrawerButton {
                    id: clearLogButton

                    theme: root.theme
                    typography: root.typography
                    label: "清空内存日志"
                    tone: "error"
                    KeyNavigation.tab: closeButton
                    KeyNavigation.backtab: copyAllButton
                    onClicked: {
                        if (root.logModel) {
                            root.logModel.clear()
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                }
            }
        }
    }

    component DrawerButton: WorkstationButton {
        id: drawerButton

        property string label: ""

        Layout.preferredWidth: 86
        text: label
        iconName: label === "关闭" ? "close" : label === "清空内存日志" ? "clear" : ""
        disabledReason: "当前操作不可用。"
    }
}

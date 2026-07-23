import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Item {
    id: root
    objectName: "taskInspectorDrawer"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var taskQueueModel: null
    property string selectedPath: ""
    property real viewportWidth: width
    property real viewportHeight: height
    property bool manualOverride: false
    property bool manualOpened: false
    property var taskDetails: ({})
    readonly property int panelWidth: 360
    readonly property bool wideViewport:
        viewportWidth >= 1900 && viewportHeight >= 1200
    readonly property bool opened:
        manualOverride ? manualOpened : wideViewport

    visible: opened
    enabled: visible
    z: 30

    function toggle() {
        manualOpened = !opened
        manualOverride = true
    }

    function close() {
        manualOpened = false
        manualOverride = true
    }

    function refreshDetails() {
        taskDetails = taskQueueModel && selectedPath.length > 0
            ? taskQueueModel.taskDetails(selectedPath)
            : ({})
    }

    function valueOr(key, fallbackText) {
        var value = taskDetails && taskDetails[key] !== undefined
            ? String(taskDetails[key] || "")
            : ""
        return value.length > 0 ? value : fallbackText
    }

    onSelectedPathChanged: refreshDetails()
    onTaskQueueModelChanged: refreshDetails()

    Connections {
        target: root.taskQueueModel
        ignoreUnknownSignals: true

        function onModelReset() {
            root.refreshDetails()
        }

        function onDataChanged() {
            root.refreshDetails()
        }

        function onRowsRemoved() {
            root.refreshDetails()
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: !root.wideViewport
        color: root.theme.overlayBackground

        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    Rectangle {
        id: inspectorPanel
        objectName: "taskInspectorPanel"

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: Math.min(root.panelWidth, parent.width)
        color: root.theme.drawerBackground
        border.color: root.theme.border
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 48
                color: root.theme.panel
                border.color: root.theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: root.theme.spacing
                    anchors.rightMargin: root.theme.spacing
                    spacing: root.theme.spacingSm

                    Text {
                        text: "任务检查器"
                        color: root.theme.textPrimary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeMedium
                        font.weight: root.typography.weightBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    WorkstationButton {
                        objectName: "closeTaskInspectorButton"
                        Layout.preferredWidth: 64
                        implicitHeight: root.theme.controlHeightSmall
                        theme: root.theme
                        typography: root.typography
                        text: "收起"
                        tone: "ghost"
                        toolTipText: "收起任务检查器"
                        onClicked: root.close()
                    }
                }
            }

            ScrollView {
                id: inspectorScroll
                objectName: "taskInspectorScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                padding: root.theme.spacing
                contentWidth: Math.max(
                    0,
                    width - leftPadding - rightPadding
                    - inspectorScrollBar.width
                )
                contentHeight: inspectorContent.implicitHeight

                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ThemeScrollBar {
                    id: inspectorScrollBar
                    theme: root.theme
                    policy: ScrollBar.AsNeeded
                }

                ColumnLayout {
                    id: inspectorContent
                    width: inspectorScroll.availableWidth
                    spacing: root.theme.spacing

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: selectedTaskContent.implicitHeight
                            + root.theme.spacing * 2
                        color: root.theme.surface
                        border.color: root.theme.border
                        radius: root.theme.radiusSmall

                        ColumnLayout {
                            id: selectedTaskContent
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: root.theme.spacing
                            spacing: 5

                            Text {
                                text: root.selectedPath.length > 0
                                    ? root.valueOr("filename", "任务已不在队列中")
                                    : "请选择一个任务"
                                color: root.theme.textPrimary
                                font.family: root.typography.fontFamily
                                font.pixelSize: root.typography.sizeBody
                                font.weight: root.typography.weightBold
                                Layout.fillWidth: true
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            }

                            Text {
                                text: root.selectedPath.length > 0
                                    ? root.valueOr("status", "未知状态")
                                        + " · "
                                        + root.valueOr("stage", "无阶段信息")
                                    : "检查器直接读取统一任务队列，不创建第二套任务状态。"
                                color: root.theme.textSecondary
                                font.family: root.typography.fontFamily
                                font.pixelSize: root.typography.sizeSmall
                                Layout.fillWidth: true
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            }
                        }
                    }

                    DetailField {
                        label: "源路径"
                        value: root.valueOr("path", "未选择任务")
                    }

                    DetailField {
                        label: "输入与目标格式"
                        value: root.valueOr("inputFormat", "-")
                            + " → "
                            + root.valueOr("targetFormat", "-")
                    }

                    DetailField {
                        label: "参与状态"
                        value: root.valueOr("participation", "-")
                    }

                    DetailField {
                        label: "输出目录策略"
                        value: root.valueOr("outputStrategy", "-")
                            + " · "
                            + root.valueOr("outputDirectory", "未设置")
                    }

                    DetailField {
                        label: "错误详情"
                        value: root.valueOr("errorDetails", "无")
                        danger: root.valueOr("errorDetails", "").length > 0
                    }

                    DetailField {
                        label: "正式输出路径"
                        value: root.valueOr("outputPath", "尚未生成正式输出")
                    }

                    DetailField {
                        label: "歌词处理结果"
                        value: root.valueOr("lyricsResult", "尚无歌词处理结果")
                    }

                    DetailField {
                        label: "来源"
                        value: root.valueOr("sourceOrigin", "未知来源")
                            + "（"
                            + root.valueOr("sourceOriginKey", "watcher")
                            + "）"
                    }

                    DetailField {
                        label: "来源类型"
                        value: root.valueOr("sourceType", "-")
                    }
                }
            }
        }
    }

    component DetailField: Rectangle {
        property string label: ""
        property string value: ""
        property bool danger: false

        Layout.fillWidth: true
        implicitHeight: detailContent.implicitHeight + root.theme.spacing * 2
        color: root.theme.surface
        border.color: root.theme.border
        radius: root.theme.radiusSmall

        ColumnLayout {
            id: detailContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: root.theme.spacing
            spacing: 5

            Text {
                text: label
                color: root.theme.textMuted
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeTiny
                font.weight: root.typography.weightMedium
                Layout.fillWidth: true
            }

            Text {
                text: value
                color: danger ? root.theme.danger : root.theme.textSecondary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                Layout.fillWidth: true
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
        }
    }
}

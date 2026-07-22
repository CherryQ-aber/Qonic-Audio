import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

SectionCard {
    id: root
    objectName: "convertActionBar"

    property QtObject typography: Typography {}
    property var autoConvertViewModel
    property var taskQueueModel
    property var selectedPaths: []
    property bool previewMode: autoConvertViewModel ? autoConvertViewModel.previewMode : true

    implicitHeight: actionLayout.implicitHeight + theme.spacing * 2

    ColumnLayout {
        id: actionLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: theme.spacing
        spacing: 6

        Flow {
            id: actionRow
            objectName: "convertActionRow"
            Layout.fillWidth: true
            spacing: 7

            ActionButton {
                objectName: "queueStartButton"
                text: "开始转换"
                actionName: "start_convert"
                accent: true
                enabled: root.autoConvertViewModel
                    && root.autoConvertViewModel.canBatchConvert
                    && !root.autoConvertViewModel.hasBackgroundTask
                hint: root.autoConvertViewModel && root.autoConvertViewModel.isQueuePreparing
                    ? "正在读取和验证任务；完成后可开始转换。"
                    : "按任务创建时的输出参数串行执行。"
            }
            ActionButton {
                objectName: "queueConvertToButton"
                text: "转换到……"
                actionName: "convert_selected_to_directory"
                enabled: root.autoConvertViewModel
                    && root.autoConvertViewModel.canBatchConvert
                    && root.autoConvertViewModel.canMutateQueue
                    && !root.autoConvertViewModel.hasBackgroundTask
                    && root.selectedPaths.length > 0
                hint: root.selectedPaths.length > 0
                    ? "为选中任务设置本轮输出目录并开始转换。"
                    : "请先在任务队列中选择任务。"
            }
            ActionButton {
                objectName: "queueCancelButton"
                text: "取消当前任务"
                actionName: "cancel_current_task"
                enabled: root.autoConvertViewModel
                    && root.autoConvertViewModel.canCancelCurrentTask
                hint: "终止当前转换；后续任务保留在队列。"
            }
            ActionButton {
                objectName: "queueStopButton"
                text: "完成当前后停止"
                actionName: "stop_after_current_task"
                enabled: root.autoConvertViewModel
                    && root.autoConvertViewModel.canStopAfterCurrentTask
                hint: "当前任务完成后保留后续等待任务。"
            }
            ActionButton {
                objectName: "queueRefreshButton"
                text: "刷新队列"
                iconName: "refresh"
                actionName: "refresh_queue"
                enabled: true
                hint: "读取当前任务队列状态。"
            }
            ActionButton {
                text: "清除终态"
                actionName: "clear_terminal_items"
                objectName: "queueClearButton"
                enabled: root.autoConvertViewModel
                    && root.autoConvertViewModel.canMutateQueue
                    && root.taskQueueModel
                    && root.taskQueueModel.clearableCount > 0
                hint: "只清除已完成/失败记录，不删除源文件或输出。"
            }
            ActionButton {
                text: "重试失败"
                actionName: "retry_failed_items"
                objectName: "queueRetryButton"
                enabled: root.autoConvertViewModel
                    && root.autoConvertViewModel.canMutateQueue
                    && root.taskQueueModel
                    && root.taskQueueModel.retryableCount > 0
                hint: "重新验证失败任务后入列。"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8
            Text {
                id: actionRestrictionText
                objectName: "actionRestrictionText"
                text: root.previewMode
                    ? "预览模式不会执行文件操作。"
                    : "串行执行 · no-clobber · 源文件保留"
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            Text {
                text: root.autoConvertViewModel
                    ? "最近操作：" + root.autoConvertViewModel.lastOperation : ""
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                maximumLineCount: 1
                ToolTip.visible: operationMouse.containsMouse && text.length > 0
                ToolTip.text: text
                MouseArea {
                    id: operationMouse
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
        }
    }

    component ActionButton: WorkstationButton {
        property string actionName: ""
        property string hint: ""
        property bool accent: false

        objectName: "convertActionButton"
        width: actionName === "stop_after_current_task" ? 138 : 116
        implicitWidth: width
        theme: root.theme
        typography: root.typography
        implicitHeight: theme.controlHeightSmall
        tone: accent ? "primary" : "secondary"
        disabledReason: hint
        onClicked: root.runAction(actionName)
        ToolTip.visible: hovered && hint.length > 0
        ToolTip.text: hint
    }

    function runAction(actionName) {
        if (!autoConvertViewModel) {
            return
        }

        if (actionName === "choose_input_files") {
            autoConvertViewModel.choose_input_files()
        } else if (actionName === "choose_scan_folder") {
            autoConvertViewModel.choose_scan_folder()
        } else if (actionName === "cancel_directory_scan") {
            autoConvertViewModel.cancel_directory_scan()
        } else if (actionName === "start_monitor") {
            autoConvertViewModel.start_monitor()
        } else if (actionName === "stop_monitor") {
            autoConvertViewModel.stop_monitor()
        } else if (actionName === "scan_existing_files") {
            autoConvertViewModel.scan_existing_files()
        } else if (actionName === "refresh_queue") {
            autoConvertViewModel.refresh_queue()
        } else if (actionName === "start_convert") {
            autoConvertViewModel.start_convert()
        } else if (actionName === "convert_selected_to_directory") {
            autoConvertViewModel.convert_selected_to_directory(root.selectedPaths)
        } else if (actionName === "cancel_current_task") {
            autoConvertViewModel.cancel_current_task()
        } else if (actionName === "stop_after_current_task") {
            autoConvertViewModel.stop_after_current_task()
        } else if (actionName === "convert_to_placeholder") {
            autoConvertViewModel.convert_to_placeholder()
        } else if (actionName === "clear_terminal_items") {
            autoConvertViewModel.clear_terminal_items()
        } else if (actionName === "retry_failed_items") {
            autoConvertViewModel.retry_failed_items()
        } else if (actionName === "apply_target_format_placeholder") {
            autoConvertViewModel.apply_target_format_placeholder()
        }
    }
}

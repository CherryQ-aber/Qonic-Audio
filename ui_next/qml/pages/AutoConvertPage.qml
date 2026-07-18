import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    // Keep the context objects under page-local names before passing them to
    // components that expose identically named properties.  Without this,
    // QML resolves ``autoConvertViewModel: autoConvertViewModel`` as a
    // self-reference inside the child component and the action controls see
    // a null ViewModel.
    property var autoConvertBridge: autoConvertViewModel
    property var taskQueueBridge: taskQueueModel

    ColumnLayout {
        id: workspaceLayout
        anchors.fill: parent
        spacing: theme.spacing

        Rectangle {
            id: compactEntryBar
            objectName: "autoConvertCompactEntryBar"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: entryContent.implicitHeight + theme.spacing * 2
            color: theme.panel
            border.color: autoConvertViewModel.previewMode ? theme.warning : theme.border
            radius: theme.radiusSmall

            ColumnLayout {
                id: entryContent
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: theme.spacing
                spacing: 7

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: theme.spacing

                    Text {
                        text: "自动转码"
                        color: theme.textPrimary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeMedium
                        font.weight: typography.weightBold
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    StatusBadge {
                        theme: root.theme
                        typography: root.typography
                        label: autoConvertViewModel.previewMode ? "预览模式" : autoConvertViewModel.monitoringStatus
                        tone: autoConvertViewModel.previewMode ? "muted" : autoConvertViewModel.isMonitoring ? "success" : "accent"
                    }

                    StatusBadge {
                        theme: root.theme
                        typography: root.typography
                        label: taskQueueModel.waitingCount + " 等待 · "
                            + taskQueueModel.processingCount + " 处理中 · "
                            + taskQueueModel.failedCount + " 失败"
                        tone: taskQueueModel.failedCount > 0 ? "danger"
                            : taskQueueModel.processingCount > 0 ? "warning" : "muted"
                    }
                }

                Flow {
                    id: entryActions
                    objectName: "autoConvertEntryActions"
                    Layout.fillWidth: true
                    spacing: 7

                    ToolbarButton {
                        text: "添加文件"
                        enabled: autoConvertViewModel.canAddFiles
                        hint: "选择一个或多个支持的音频并加入统一任务队列。"
                        onClicked: autoConvertViewModel.choose_input_files()
                    }
                    ToolbarButton {
                        text: autoConvertViewModel.isDirectoryScanning ? "取消扫描" : "扫描目录"
                        enabled: autoConvertViewModel.isDirectoryScanning
                            || autoConvertViewModel.canScanDirectories
                        hint: autoConvertViewModel.isDirectoryScanning
                            ? "取消后保留已经成功入队的任务。"
                            : "后台扫描目录，支持文件直接进入统一任务队列。"
                        onClicked: {
                            if (autoConvertViewModel.isDirectoryScanning)
                                autoConvertViewModel.cancel_directory_scan()
                            else
                                autoConvertViewModel.choose_scan_folder()
                        }
                    }
                    ToolbarButton {
                        text: autoConvertViewModel.isMonitoring ? "停止监听" : "开始监听"
                        enabled: autoConvertViewModel.canControlWatcher
                        hint: "监听只负责发现文件并入队，不会自动开始转换。"
                        onClicked: {
                            if (autoConvertViewModel.isMonitoring)
                                autoConvertViewModel.stop_monitor()
                            else
                                autoConvertViewModel.start_monitor()
                        }
                    }
                    CompactSummary {
                        label: "目标格式"
                        value: autoConvertViewModel.globalTargetFormatLabel
                        preferredWidth: 154
                    }
                    CompactSummary {
                        label: "输出"
                        value: autoConvertViewModel.outputFolder
                        preferredWidth: Math.min(310, Math.max(220, entryActions.width * 0.28))
                        middleElide: true
                    }
                    CompactSummary {
                        label: "监听"
                        value: autoConvertViewModel.watchFolder
                        preferredWidth: Math.min(270, Math.max(190, entryActions.width * 0.24))
                        middleElide: true
                    }
                }

                Text {
                    visible: autoConvertViewModel.previewMode
                    text: "预览模式不会监听、入队、转换、保存设置或修改 config.json。"
                    color: theme.warning
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeTiny
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }

        TaskQueueView {
            id: taskQueue
            objectName: "autoConvertPrimaryQueue"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 190
            Layout.minimumWidth: 0
            theme: root.theme
            typography: root.typography
            queueModel: root.taskQueueBridge
            autoConvertViewModel: root.autoConvertBridge
        }

        ScanSummaryBar {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            theme: root.theme
            typography: root.typography
            viewModel: root.autoConvertBridge
        }

        ConvertActionBar {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            theme: root.theme
            typography: root.typography
            autoConvertViewModel: root.autoConvertBridge
            taskQueueModel: root.taskQueueBridge
            selectedPaths: taskQueue.selectedPaths
        }
    }

    component CompactSummary: Rectangle {
        property string label: ""
        property string value: ""
        property int preferredWidth: 180
        property bool middleElide: false

        width: preferredWidth
        implicitWidth: preferredWidth
        implicitHeight: theme.controlHeightSmall
        color: theme.surface
        border.color: theme.border
        radius: theme.radiusSmall

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 6

            Text {
                text: parent.parent.label
                color: theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
            }

            Text {
                id: compactSummaryValue
                text: parent.parent.value || "未设置"
                color: parent.parent.value ? theme.textSecondary : theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: parent.parent.middleElide ? Text.ElideMiddle : Text.ElideRight
                maximumLineCount: 1

                ToolTip.visible: summaryMouse.containsMouse && parent.parent.value.length > 0
                ToolTip.text: parent.parent.value

                MouseArea {
                    id: summaryMouse
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
        }
    }

    component ToolbarButton: WorkstationButton {
        property string hint: ""

        width: 112
        implicitWidth: 112
        implicitHeight: theme.controlHeightSmall
        theme: root.theme
        typography: root.typography
        tone: "secondary"
        disabledReason: hint
        ToolTip.visible: hovered && hint.length > 0
        ToolTip.text: hint
    }
}

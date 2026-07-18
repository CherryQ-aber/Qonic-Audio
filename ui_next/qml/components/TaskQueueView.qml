import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

SectionCard {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var queueModel
    property var sourceModel: queueModel
    property var autoConvertViewModel
    property bool previewMode: autoConvertViewModel ? autoConvertViewModel.previewMode : true
    property bool pageActive: true
    property bool interactionEnabled: pageActive
    property bool inspectorOpened: false
    property var selectedPaths: []
    property int selectionAnchorIndex: -1
    property real preservedQueueContentY: 0
    property bool queueViewRestorePending: false

    signal inspectorToggleRequested()

    implicitHeight: 260
    Layout.minimumWidth: 0
    enabled: pageActive && interactionEnabled

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: "任务队列"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: queueModel.count + " 个当前任务"
                tone: root.sourceModel && root.sourceModel.failedCount > 0
                    ? "danger"
                    : "muted"
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.selectedPaths.length + " 个已选"
                tone: root.selectedPaths.length > 0 ? "accent" : "muted"
            }

            WorkstationButton {
                objectName: "toggleTaskInspectorButton"
                Layout.preferredWidth: 98
                implicitHeight: root.theme.controlHeightSmall
                theme: root.theme
                typography: root.typography
                text: root.inspectorOpened ? "收起检查器" : "任务检查器"
                tone: root.inspectorOpened ? "primary" : "ghost"
                toolTipText: root.inspectorOpened
                    ? "收起当前任务检查器"
                    : "查看选中任务的路径、输出、错误和来源详情"
                onClicked: root.inspectorToggleRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: theme.surface
            border.color: theme.border
            radius: theme.radiusSmall

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 13
                anchors.rightMargin: 10
                spacing: 10

                HeaderText { text: "参与"; Layout.preferredWidth: 56 }
                HeaderText { text: "文件名"; Layout.fillWidth: true }
                HeaderText { text: "输入格式"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignHCenter }
                HeaderText { text: "目标格式"; Layout.preferredWidth: 170 }
                HeaderText { text: "输出策略"; Layout.preferredWidth: 104 }
                HeaderText { text: "状态"; Layout.preferredWidth: 92; horizontalAlignment: Text.AlignHCenter }
                HeaderText { text: "当前阶段 / 错误"; Layout.preferredWidth: 150 }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 132
            color: theme.surface
            border.color: theme.border
            radius: theme.radiusSmall
            clip: true

            ListView {
                id: queueList
                objectName: "taskQueueListView"

                anchors.fill: parent
                anchors.margins: 8
                clip: true
                spacing: 6
                model: root.queueModel
                ScrollBar.vertical: ThemeScrollBar {
                    objectName: "taskQueueVerticalScrollBar"
                    theme: root.theme
                    policy: ScrollBar.AsNeeded
                }

                delegate: TaskRowDelegate {
                    width: queueList.width
                    interactionEnabled: root.interactionEnabled
                    theme: root.theme
                    typography: root.typography
                    rowIndex: index
                    fileName: model.filename
                    sourceFormat: model.format
                    targetFormat: model.targetFormat
                    effectiveTargetFormat: model.effectiveTargetFormat
                    targetFormatLabel: model.targetFormatLabel
                    outputStrategyLabel: model.outputStrategyLabel
                    outputDirectoryOverride: model.outputDirectoryOverride
                    sameFormatWarning: model.sameFormatWarning
                    plannedOutputPath: model.plannedOutputPath
                    outputNameConflict: model.outputNameConflict
                    queueWarningText: model.queueWarningText
                    statusLabel: model.statusLabel
                    statusDetail: model.statusDetail
                    statusColor: model.statusColor
                    statusTone: model.statusTone
                    path: model.path
                    stage: model.stage
                    errorSummary: model.errorSummary
                    enabledForRun: model.enabledForRun
                    selected: root.isPathSelected(model.path)
                    selectedPaths: root.selectedPaths
                    canConvert: model.canConvert
                        && root.autoConvertViewModel
                        && root.autoConvertViewModel.canBatchConvert
                        && !root.autoConvertViewModel.hasBackgroundTask
                    canRetry: model.canRetry && root.autoConvertViewModel && root.autoConvertViewModel.canMutateQueue
                    canRemove: model.canRemove && root.autoConvertViewModel && root.autoConvertViewModel.canMutateQueue
                    canOpenOutput: model.canOpenOutput
                    canLoadSource: model.canLoadSource
                    sourcePlaybackDisabledReason: model.sourcePlaybackDisabledReason
                    canLoadOutput: model.canLoadOutput
                    outputPlaybackDisabledReason: model.outputPlaybackDisabledReason
                    canChangeRunPolicy: model.canChangeRunPolicy && !root.previewMode && root.autoConvertViewModel && root.autoConvertViewModel.canMutateQueue
                    canChangeOutputDirectory: model.canChangeOutputDirectory && !root.previewMode && root.autoConvertViewModel && root.autoConvertViewModel.canMutateQueue
                    canChangeTargetFormat: model.canChangeTargetFormat && !root.previewMode && root.autoConvertViewModel && root.autoConvertViewModel.canMutateQueue
                    readOnly: root.previewMode || !model.canChangeTargetFormat || !root.autoConvertViewModel || !root.autoConvertViewModel.canMutateQueue
                    formatOptions: root.autoConvertViewModel.targetFormats
                    onSelectionRequested: function(filePath, rowIndex, modifiers, rightClick) {
                        root.updateSelection(filePath, rowIndex, modifiers, rightClick)
                    }
                    onEnabledForRunRequested: function(paths, enabled) {
                        root.autoConvertViewModel.set_tasks_enabled_for_run(paths, enabled)
                    }
                    onTargetFormatsRequested: function(paths, targetFormat) {
                        root.autoConvertViewModel.set_tasks_target_format(paths, targetFormat)
                    }
                    onOutputDirectoryRequested: function(paths) {
                        root.autoConvertViewModel.choose_tasks_output_directory(paths)
                    }
                    onResetOutputDirectoryRequested: function(paths) {
                        root.autoConvertViewModel.reset_tasks_output_directory(paths)
                    }
                    onRetryRequested: function(paths) {
                        root.autoConvertViewModel.retry_failed_tasks(paths)
                    }
                    onRemoveRequested: function(paths) {
                        root.autoConvertViewModel.remove_pending_items(paths)
                        root.pruneSelection()
                    }
                    onOpenSourceRequested: function(filePath) {
                        root.autoConvertViewModel.open_task_source(filePath)
                    }
                    onOpenOutputRequested: function(filePath) {
                        root.autoConvertViewModel.open_task_output(filePath)
                    }
                    onLoadSourceToPlayerRequested: function(filePath) {
                        root.autoConvertViewModel.load_task_source_to_player(filePath)
                    }
                    onLoadOutputToPlayerRequested: function(filePath) {
                        root.autoConvertViewModel.load_task_output_to_player(filePath)
                    }
                    onOpenInEditorRequested: function(filePath) {
                        root.autoConvertViewModel.open_task_in_editor(filePath)
                    }
                    onConvertRequested: function(filePath) {
                        root.autoConvertViewModel.start_convert_item(filePath)
                    }
                    onConvertSelectedRequested: function(paths) {
                        root.autoConvertViewModel.start_convert_selected(paths)
                    }
                }
            }

            EmptyState {
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 480)
                visible: queueModel.count === 0
                theme: root.theme
                typography: root.typography
                title: root.sourceModel && root.sourceModel.totalCount > 0
                    ? "当前筛选下没有任务"
                    : "当前没有任务"
                detail: root.sourceModel && root.sourceModel.totalCount > 0
                    ? "可以切换顶部任务视图查看其他状态的任务。"
                    : root.previewMode
                        ? "预览模式下不能加入任务队列。"
                        : "添加文件、拖入文件或扫描目录后，任务会显示在这里。"
            }

            DropArea {
                id: dropArea
                objectName: "autoConvertDropArea"
                anchors.fill: parent
                enabled: root.pageActive && root.interactionEnabled
                onEntered: drag.accepted = true
                onDropped: function(drop) {
                    root.autoConvertViewModel.enqueue_dropped_items(drop.urls)
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: dropArea.containsDrag
                color: Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.12)
                border.color: theme.accent
                border.width: 1
                radius: theme.radiusSmall

                Behavior on color { ColorAnimation { duration: theme.durationFast } }

                Text {
                    anchors.centerIn: parent
                    text: "释放后，文件直接入队；文件夹在后台扫描后入队。"
                    color: theme.textPrimary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeMedium
                    font.weight: typography.weightBold
                }
            }
        }
    }

    Connections {
        target: root.queueModel
        ignoreUnknownSignals: true

        function onModelAboutToBeReset() {
            root.rememberQueueViewPosition()
        }

        function onModelReset() {
            root.pruneSelection()
            root.restoreQueueViewPosition()
        }

        function onRowsAboutToBeRemoved() {
            root.rememberQueueViewPosition()
        }

        function onRowsRemoved() {
            root.pruneSelection()
            root.restoreQueueViewPosition()
        }

        function onLayoutAboutToBeChanged() {
            root.rememberQueueViewPosition()
        }

        function onLayoutChanged() {
            root.pruneSelection()
            root.restoreQueueViewPosition()
        }

        function onFilterChanged() {
            root.pruneSelection()
        }
    }

    function rememberQueueViewPosition() {
        if (!queueList)
            return
        root.preservedQueueContentY = queueList.contentY
        root.queueViewRestorePending = true
    }

    function restoreQueueViewPosition() {
        if (!root.queueViewRestorePending)
            return
        Qt.callLater(function() {
            var maximumContentY = Math.max(
                0,
                queueList.contentHeight - queueList.height
            )
            queueList.contentY = Math.max(
                0,
                Math.min(root.preservedQueueContentY, maximumContentY)
            )
            root.queueViewRestorePending = false
        })
    }

    function isPathSelected(filePath) {
        return root.selectedPaths.indexOf(filePath) >= 0
    }

    function updateSelection(filePath, rowIndex, modifiers, rightClick) {
        var ctrl = (modifiers & Qt.ControlModifier) !== 0
        var shift = (modifiers & Qt.ShiftModifier) !== 0
        var updated = root.selectedPaths.slice()

        if (rightClick && updated.indexOf(filePath) < 0) {
            updated = [filePath]
            root.selectionAnchorIndex = rowIndex
        } else if (shift && root.selectionAnchorIndex >= 0 && root.queueModel) {
            if (!ctrl) {
                updated = []
            }
            var first = Math.min(root.selectionAnchorIndex, rowIndex)
            var last = Math.max(root.selectionAnchorIndex, rowIndex)
            for (var row = first; row <= last; ++row) {
                var path = root.queueModel.pathAt(row)
                if (path && updated.indexOf(path) < 0) {
                    updated.push(path)
                }
            }
        } else if (ctrl) {
            var index = updated.indexOf(filePath)
            if (index >= 0) {
                updated.splice(index, 1)
            } else {
                updated.push(filePath)
            }
            root.selectionAnchorIndex = rowIndex
        } else {
            updated = [filePath]
            root.selectionAnchorIndex = rowIndex
        }
        root.selectedPaths = updated
    }

    function pruneSelection() {
        if (!root.queueModel) {
            root.selectedPaths = []
            root.selectionAnchorIndex = -1
            return
        }
        var valid = []
        for (var index = 0; index < root.selectedPaths.length; ++index) {
            var path = root.selectedPaths[index]
            if (root.queueModel.containsPath(path)) {
                valid.push(path)
            }
        }
        root.selectedPaths = valid
        if (valid.length === 0) {
            root.selectionAnchorIndex = -1
        }
    }

    component HeaderText: Text {
        color: theme.textSecondary
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall
        font.weight: typography.weightMedium
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property int rowIndex: 0
    property string fileName: ""
    property string sourceFormat: ""
    property string targetFormat: ""
    property string effectiveTargetFormat: ""
    property string targetFormatLabel: ""
    property string outputStrategyLabel: ""
    property string outputDirectoryOverride: ""
    property bool sameFormatWarning: false
    property string plannedOutputPath: ""
    property bool outputNameConflict: false
    property string queueWarningText: ""
    property string statusLabel: ""
    property string statusDetail: ""
    property color statusColor: theme.textMuted
    property string statusTone: "muted"
    property string path: ""
    property string stage: ""
    property string errorSummary: ""
    property bool enabledForRun: true
    property bool selected: false
    property var selectedPaths: []
    property bool canConvert: false
    property bool canChangeTargetFormat: false
    property bool canChangeRunPolicy: false
    property bool canChangeOutputDirectory: false
    property bool canRetry: false
    property bool canRemove: false
    property bool canOpenOutput: false
    property bool canLoadSource: false
    property string sourcePlaybackDisabledReason: ""
    property bool canLoadOutput: false
    property string outputPlaybackDisabledReason: ""
    property bool readOnly: true
    property bool interactionEnabled: true
    property var formatOptions: []
    readonly property bool hasQueueWarning: sameFormatWarning || outputNameConflict
    readonly property bool stageTakesDetailPriority: statusTone === "warning"
        || statusTone === "success"
    readonly property string primaryDetailText: errorSummary
        || (stageTakesDetailPriority ? stage : queueWarningText)
        || stage
        || statusDetail
        || "无附加说明"

    enabled: interactionEnabled

    onInteractionEnabledChanged: {
        if (!interactionEnabled && taskMenu.opened)
            taskMenu.close()
    }

    signal selectionRequested(string path, int rowIndex, int modifiers, bool rightClick)
    signal enabledForRunRequested(var paths, bool enabled)
    signal targetFormatsRequested(var paths, string targetFormat)
    signal outputDirectoryRequested(var paths)
    signal resetOutputDirectoryRequested(var paths)
    signal convertRequested(string path)
    signal convertSelectedRequested(var paths)
    signal retryRequested(var paths)
    signal removeRequested(var paths)
    signal openSourceRequested(string path)
    signal openOutputRequested(string path)
    signal loadSourceToPlayerRequested(string path)
    signal loadOutputToPlayerRequested(string path)
    signal openInEditorRequested(string path)

    implicitHeight: 54
    color: root.selected
        ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.14)
        : root.hasQueueWarning
            ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.08)
            : rowIndex % 2 === 0
                ? theme.surface
                : Qt.rgba(theme.panel.r, theme.panel.g, theme.panel.b, 0.64)
    border.color: root.selected
        ? theme.accent
        : root.hasQueueWarning
            ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.52)
            : Qt.rgba(theme.border.r, theme.border.g, theme.border.b, 0.65)
    border.width: 1
    radius: theme.radiusSmall

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onClicked: function(mouse) {
            root.selectionRequested(root.path, root.rowIndex, mouse.modifiers, false)
        }
        onDoubleClicked: function(mouse) {
            root.selectionRequested(root.path, root.rowIndex, mouse.modifiers, false)
            root.loadSourceToPlayerRequested(root.path)
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 10

        CheckBox {
            id: participationCheck
            Layout.preferredWidth: 56
            checked: root.enabledForRun
            enabled: root.canChangeRunPolicy
            text: checked ? "参与" : "跳过"
            onClicked: {
                root.selectionRequested(root.path, root.rowIndex, Qt.NoModifier, false)
                root.enabledForRunRequested(root.actionPaths(), checked)
            }
            ToolTip.visible: hovered
            ToolTip.text: enabled
                ? "只控制批量转换是否包含此任务，不改变任务状态。"
                : "读取、处理或已完成任务不能修改参与策略。"
        }

        Text {
            id: fileNameText
            text: root.fileName
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeBody
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            maximumLineCount: 1

            ToolTip.visible: fileNameMouse.containsMouse && root.path.length > 0
            ToolTip.text: root.path

            MouseArea {
                id: fileNameMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                onClicked: function(mouse) {
                    root.selectionRequested(root.path, root.rowIndex, mouse.modifiers, false)
                }
                onDoubleClicked: function(mouse) {
                    root.selectionRequested(root.path, root.rowIndex, mouse.modifiers, false)
                    root.loadSourceToPlayerRequested(root.path)
                }
            }
        }

        Text {
            text: root.sourceFormat
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            horizontalAlignment: Text.AlignHCenter
            Layout.preferredWidth: 70
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text {
            text: root.targetFormatLabel
            color: root.sameFormatWarning
                ? theme.warning
                : root.targetFormat.length > 0
                    ? theme.textPrimary
                    : theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.preferredWidth: 170
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text {
            text: root.outputStrategyLabel
            color: root.outputNameConflict
                ? theme.warning
                : root.outputDirectoryOverride.length > 0
                    ? theme.textPrimary
                    : theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.preferredWidth: 104
            elide: Text.ElideRight
            maximumLineCount: 1

            ToolTip.visible: outputMouse.containsMouse
            ToolTip.text: root.outputNameConflict
                ? root.queueWarningText + "\n基础计划路径：" + root.plannedOutputPath
                : root.outputDirectoryOverride.length > 0
                    ? root.outputDirectoryOverride
                    : "跟随全局默认输出目录"

            MouseArea {
                id: outputMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
            }
        }

        StatusBadge {
            theme: root.theme
            typography: root.typography
            label: root.statusLabel
            tone: root.statusTone
            Layout.preferredWidth: 92
        }

        Text {
            text: root.primaryDetailText
            color: root.errorSummary
                ? theme.danger
                : root.queueWarningText && !root.stageTakesDetailPriority
                    ? theme.warning
                    : theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.preferredWidth: 150
            elide: Text.ElideRight
            maximumLineCount: 1

            ToolTip.visible: detailMouse.containsMouse
            ToolTip.text: root.primaryDetailText

            MouseArea {
                id: detailMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: function(mouse) {
            root.selectionRequested(root.path, root.rowIndex, mouse.modifiers, true)
            taskMenu.popup()
        }
    }

    Menu {
        id: taskMenu

        MenuItem {
            text: "载入源文件到播放器"
            enabled: root.canLoadSource
            ToolTip.visible: hovered && !enabled
            ToolTip.text: root.sourcePlaybackDisabledReason
            onTriggered: root.loadSourceToPlayerRequested(root.path)
        }

        MenuItem {
            text: "载入转换结果到播放器"
            enabled: root.canLoadOutput
            ToolTip.visible: hovered && !enabled
            ToolTip.text: root.outputPlaybackDisabledReason
            onTriggered: root.loadOutputToPlayerRequested(root.path)
        }

        MenuItem {
            text: "在音频编辑中打开"
            enabled: root.canLoadSource
            ToolTip.visible: hovered && !enabled
            ToolTip.text: root.sourcePlaybackDisabledReason
            onTriggered: root.openInEditorRequested(root.path)
        }

        MenuSeparator {}

        MenuItem {
            text: "转换此文件"
            enabled: root.canConvert
            onTriggered: root.convertRequested(root.path)
        }

        MenuItem {
            text: "转换选中文件"
            enabled: root.selectedPaths.length > 0
            onTriggered: root.convertSelectedRequested(root.actionPaths())
        }

        MenuSeparator {}

        MenuItem {
            text: "参与本轮转换"
            enabled: root.canChangeRunPolicy
            onTriggered: root.enabledForRunRequested(root.actionPaths(), true)
        }

        MenuItem {
            text: "本轮跳过"
            enabled: root.canChangeRunPolicy
            onTriggered: root.enabledForRunRequested(root.actionPaths(), false)
        }

        Menu {
            id: formatMenu
            title: "目标格式"
            enabled: root.canChangeTargetFormat

            MenuItem {
                text: "跟随全局格式"
                onTriggered: root.targetFormatsRequested(root.actionPaths(), "")
            }

            Repeater {
                model: root.formatOptions
                delegate: MenuItem {
                    required property var modelData
                    text: "转换为 " + modelData.label
                    onTriggered: root.targetFormatsRequested(root.actionPaths(), modelData.value)
                }
            }
        }

        Menu {
            title: "输出目录"
            enabled: root.canChangeOutputDirectory

            MenuItem {
                text: "使用默认输出目录"
                onTriggered: root.resetOutputDirectoryRequested(root.actionPaths())
            }

            MenuItem {
                text: "本轮转换到……"
                onTriggered: root.outputDirectoryRequested(root.actionPaths())
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "重试失败任务"
            enabled: root.canRetry
            onTriggered: root.retryRequested(root.actionPaths())
        }

        MenuItem {
            text: "移除任务"
            enabled: root.canRemove
            onTriggered: root.removeRequested(root.actionPaths())
        }

        MenuItem {
            text: "打开源文件位置"
            enabled: root.path.length > 0
            onTriggered: root.openSourceRequested(root.path)
        }

        MenuItem {
            text: "打开输出位置"
            enabled: root.canOpenOutput
            onTriggered: root.openOutputRequested(root.path)
        }
    }

    function actionPaths() {
        if (root.selected && root.selectedPaths.length > 0) {
            return root.selectedPaths
        }
        return [root.path]
    }
}

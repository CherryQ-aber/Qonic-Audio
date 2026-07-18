import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "scanSummaryBar"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel

    implicitHeight: 32
    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall

    RowLayout {
        id: summaryLayout
        anchors.fill: parent
        anchors.leftMargin: 9
        anchors.rightMargin: 9
        spacing: 9

        Text {
            text: "扫描摘要"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightBold
        }

        SummaryItem {
            label: "扫描文件"
            value: root.viewModel ? root.viewModel.scanTotalCount : 0
        }

        SummaryItem {
            label: "新增任务"
            value: root.viewModel ? root.viewModel.scanAddedCount : 0
        }

        SummaryItem {
            label: "重复跳过"
            value: root.viewModel ? root.viewModel.scanDuplicateCount : 0
        }

        SummaryItem {
            label: "不支持格式"
            value: root.viewModel ? root.viewModel.scanUnsupportedCount : 0
        }

        Item {
            Layout.fillWidth: true
        }

        StatusBadge {
            theme: root.theme
            typography: root.typography
            label: root.viewModel ? root.viewModel.scanStatusLabel : "尚未扫描"
            tone: root.viewModel && root.viewModel.isDirectoryScanning
                ? "warning"
                : root.viewModel && root.viewModel.scanWasCancelled
                    ? "muted"
                    : "success"
        }
    }

    component SummaryItem: RowLayout {
        property string label: ""
        property var value: 0

        spacing: 4

        Text {
            text: label
            color: theme.muted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTiny
        }

        Text {
            text: value
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightBold
        }
    }
}

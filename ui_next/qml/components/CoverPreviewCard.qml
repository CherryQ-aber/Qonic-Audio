import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel: null
    property string selectionSource: "metadata_page"

    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall
    implicitHeight: coverContent.implicitHeight + (theme.spacing + 4) * 2

    ColumnLayout {
        id: coverContent
        anchors.fill: parent
        anchors.margins: theme.spacing + 4
        spacing: theme.spacing

        Text {
            text: "封面只读预览"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeMedium
            font.weight: typography.weightBold
            Layout.fillWidth: true
        }

        StatusBadge {
            theme: root.theme
            typography: root.typography
            label: root.viewModel && root.viewModel.coverReadEnabled
                ? "封面信息已就绪"
                : "预览模式"
            tone: root.viewModel && root.viewModel.coverReadEnabled
                ? "accent"
                : "muted"
        }

        Text {
            text: root.viewModel && root.viewModel.coverReadEnabled
                ? "封面可供查看；替换、移除和恢复请在文件信息页面作为草稿处理。"
                : "预览模式：封面区域为占位显示，不读取真实封面。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 174
            Layout.preferredHeight: 174
            color: theme.surface
            border.color: theme.border
            radius: theme.radiusSmall
            clip: true

            Image {
                anchors.fill: parent
                anchors.margins: 8
                source: root.viewModel ? root.viewModel.coverImageUrl : ""
                fillMode: Image.PreserveAspectFit
                visible: root.viewModel && root.viewModel.hasCover && source !== ""
            }

            Text {
                anchors.centerIn: parent
                width: parent.width - 28
                text: root.viewModel && root.viewModel.hasCover ? "检测到封面，未生成预览" : "当前无可预览封面"
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeBody
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: !root.viewModel || !root.viewModel.hasCover || (root.viewModel.coverImageUrl === "")
            }
        }

        InfoRow {
            label: "封面状态"
            value: root.viewModel ? root.viewModel.coverStatus : "未读取"
        }

        InfoRow {
            label: "当前文件"
            value: root.viewModel ? root.viewModel.currentFileName : "当前无选中文件"
        }

        InfoRow {
            label: "MIME"
            value: root.viewModel ? root.viewModel.coverMime : "-"
        }

        InfoRow {
            label: "原始大小"
            value: root.viewModel ? root.viewModel.coverSizeText : "-"
        }

        InfoRow {
            label: "图片尺寸"
            value: root.viewModel && root.viewModel.coverDimensions !== undefined
                ? root.viewModel.coverDimensions
                : "-"
        }

        InfoRow {
            label: "读取后端"
            value: root.viewModel ? root.viewModel.readBackend : "未调用"
        }

        InfoRow {
            label: "错误信息"
            value: root.viewModel && root.viewModel.lastReadError !== ""
                ? root.viewModel.lastReadError
                : "-"
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            PreviewButton {
                text: "选择音频读取封面"
                Layout.fillWidth: true
                onClicked: fileSessionViewModel.chooseAudioFile(root.selectionSource)
            }

            PreviewButton {
                text: "重新读取"
                enabled: fileSessionViewModel && fileSessionViewModel.hasCurrentFile
                onClicked: fileSessionViewModel.reloadCurrentFile()
            }
        }

        PreviewButton {
            text: "清除封面预览"
            Layout.fillWidth: true
            enabled: fileSessionViewModel && fileSessionViewModel.hasCurrentFile
            onClicked: fileSessionViewModel.clearCurrentFile()
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            DisabledAction { text: "导入封面" }
            DisabledAction { text: "写入封面" }
            DisabledAction { text: "移除封面" }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            DisabledAction { text: "恢复封面" }
            DisabledAction { text: "覆盖封面" }
        }

        Text {
            text: "封面仅供预览；导入、移除、恢复、覆盖和写入操作尚未开放。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

    }

    component InfoRow: RowLayout {
        property string label: ""
        property string value: ""

        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 8

        Text {
            text: label
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.preferredWidth: 66
            Layout.minimumWidth: 0
        }

        Text {
            text: value
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
    }

    component PreviewButton: Button {
        width: 160
        implicitWidth: width
        implicitHeight: 29
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall

        contentItem: Text {
            text: parent.text
            color: parent.enabled ? theme.textPrimary : theme.muted
            font: parent.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        background: Rectangle {
            color: parent.enabled ? theme.surface : Qt.rgba(theme.muted.r, theme.muted.g, theme.muted.b, 0.08)
            border.color: parent.enabled ? theme.border : Qt.rgba(theme.border.r, theme.border.g, theme.border.b, 0.55)
            radius: theme.radiusSmall
        }
    }

    component DisabledAction: Button {
        enabled: false
        width: 126
        implicitWidth: width
        implicitHeight: 27
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeTiny

        contentItem: Text {
            text: parent.text
            color: theme.muted
            font: parent.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        background: Rectangle {
            color: Qt.rgba(theme.muted.r, theme.muted.g, theme.muted.b, 0.08)
            border.color: Qt.rgba(theme.border.r, theme.border.g, theme.border.b, 0.45)
            radius: theme.radiusSmall
        }
    }
}

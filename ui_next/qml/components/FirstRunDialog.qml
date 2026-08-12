import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Dialog {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel: null

    modal: true
    visible: Boolean(viewModel && viewModel.required)
    title: "Qonic Audio · 首次启动"
    closePolicy: Popup.NoAutoClose
    standardButtons: Dialog.NoButton
    anchors.centerIn: parent
    width: Math.min(620, parent ? parent.width - theme.spacingXl * 2 : 620)

    background: Rectangle {
        color: theme.panelBackgroundRaised
        border.color: theme.borderStrong
        border.width: 1
        radius: theme.radiusLarge
    }

    contentItem: ColumnLayout {
        spacing: theme.spacingMd

        Text {
            Layout.fillWidth: true
            text: "初始化监听目录"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTitle
            font.weight: typography.weightBold
        }

        Text {
            Layout.fillWidth: true
            text: !root.viewModel || root.viewModel.candidateCount === 0
                ? "暂未自动检测到支持的音乐下载目录。你可以手动选择，也可以稍后在设置中配置。"
                : root.viewModel.candidateCount === 1
                    ? "检测到可能的音乐下载目录。是否将此目录设为自动监听目录？"
                    : "检测到多个可用目录。请选择一个目录后再确认。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeBody
            wrapMode: Text.WordWrap
        }

        FormatSelector {
            Layout.fillWidth: true
            visible: Boolean(root.viewModel && root.viewModel.candidateCount > 0)
            theme: root.theme
            typography: root.typography
            options: root.viewModel ? root.viewModel.candidateOptions : []
            value: root.viewModel ? root.viewModel.selectedPath : ""
            onFormatSelected: root.viewModel.selectCandidate(value)
        }

        Text {
            Layout.fillWidth: true
            visible: Boolean(root.viewModel && root.viewModel.statusMessage.length > 0)
            text: root.viewModel ? root.viewModel.statusMessage : ""
            color: text.indexOf("失败") >= 0 || text.indexOf("不可用") >= 0
                ? theme.error : theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            text: "这里只保存目录设置，不会立即扫描、监听或转换文件。"
            color: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingSm

            WorkstationButton {
                theme: root.theme
                typography: root.typography
                text: "选择其他目录"
                onClicked: root.viewModel.chooseOtherDirectory()
            }
            Item { Layout.fillWidth: true }
            WorkstationButton {
                theme: root.theme
                typography: root.typography
                text: "暂时跳过"
                tone: "ghost"
                onClicked: root.viewModel.skip()
            }
            WorkstationButton {
                theme: root.theme
                typography: root.typography
                text: "使用此目录"
                tone: "primary"
                enabled: Boolean(root.viewModel && root.viewModel.selectedPath.length > 0)
                onClicked: root.viewModel.useSelectedDirectory()
            }
        }
    }
}

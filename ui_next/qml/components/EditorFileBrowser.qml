import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

SectionCard {
    id: root

    property QtObject typography: Typography {}
    property var viewModel: null
    property var fileSession: null

    implicitHeight: browserContent.implicitHeight + theme.spacing * 2

    function formatSize(byteCount) {
        var bytes = Number(byteCount || 0)
        if (bytes >= 1024 * 1024)
            return (bytes / (1024 * 1024)).toFixed(1) + " MB"
        if (bytes >= 1024)
            return (bytes / 1024).toFixed(1) + " KB"
        return bytes + " B"
    }

    ColumnLayout {
        id: browserContent
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.theme.spacing
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2

                Text {
                    text: "工作区文件浏览"
                    color: root.theme.textPrimary
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeMedium
                    font.weight: root.typography.weightBold
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
                Text {
                    text: "只读取所选目录的第一层；选中条目后仍需显式载入工作区。"
                    color: root.theme.textSecondary
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeSmall
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: !root.viewModel
                    ? "未连接"
                    : root.viewModel.isLoading
                        ? "读取中"
                        : root.viewModel.browserEnabled
                            ? root.viewModel.itemCount + " 个文件"
                            : "只读预览"
                tone: root.viewModel && root.viewModel.isLoading
                    ? "warning"
                    : root.viewModel && root.viewModel.browserEnabled
                        ? "accent"
                        : "muted"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            PathField {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
                label: "浏览目录"
                path: root.viewModel && root.viewModel.folderPath.length > 0
                    ? root.viewModel.folderPath
                    : ""
                browseEnabled: false
            }

            BrowserButton {
                text: "选择目录"
                enabled: root.viewModel && root.viewModel.browserEnabled && !root.viewModel.isLoading
                onClicked: root.viewModel.chooseFolder()
            }
            BrowserButton {
                text: "刷新"
                enabled: root.viewModel && root.viewModel.browserEnabled
                    && root.viewModel.folderPath.length > 0 && !root.viewModel.isLoading
                onClicked: root.viewModel.scanFolder(root.viewModel.folderPath)
            }
            BrowserButton {
                text: "清除"
                enabled: root.viewModel && (root.viewModel.folderPath.length > 0 || root.viewModel.itemCount > 0)
                onClicked: root.viewModel.clear()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.viewModel && root.viewModel.itemCount > 0 ? 190 : 92
            color: root.theme.surface
            border.color: root.theme.border
            radius: root.theme.radiusSmall
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 5

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8
                    HeaderText { text: "文件名"; Layout.fillWidth: true }
                    HeaderText { text: "格式"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignHCenter }
                    HeaderText { text: "大小"; Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight }
                    HeaderText { text: "工作区"; Layout.preferredWidth: 74; horizontalAlignment: Text.AlignHCenter }
                }

                ListView {
                    id: browserList
                    objectName: "audioEditorBrowserList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 4
                    model: root.viewModel ? root.viewModel.items : []

                    delegate: Rectangle {
                        id: browserRow
                        required property var modelData
                        readonly property bool selected: root.viewModel
                            && root.viewModel.selectedFilePath === modelData.path
                        readonly property bool loaded: root.fileSession
                            && root.fileSession.currentFilePath === modelData.path
                        width: browserList.width
                        height: 31
                        color: selected
                            ? root.theme.selectedBackground
                            : rowMouse.containsMouse
                                ? root.theme.hoverBackground
                                : loaded
                                    ? Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, 0.08)
                                    : root.theme.panel
                        border.color: selected
                            ? root.theme.selectedIndicator
                            : loaded
                                ? root.theme.accent
                                : root.theme.borderNormal
                        radius: root.theme.radiusSmall

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 9
                            anchors.rightMargin: 9
                            spacing: 8
                            RowText { text: browserRow.modelData.name || "-"; Layout.fillWidth: true; elide: Text.ElideMiddle }
                            RowText { text: browserRow.modelData.format || "-"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignHCenter }
                            RowText { text: root.formatSize(browserRow.modelData.size); Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight }
                            RowText {
                                text: browserRow.loaded ? "已载入" : browserRow.selected ? "已选中" : "-"
                                color: browserRow.loaded || browserRow.selected ? root.theme.accent : root.theme.muted
                                Layout.preferredWidth: 74
                                horizontalAlignment: Text.AlignHCenter
                            }
                        }

                        ToolTip.visible: rowMouse.containsMouse
                        ToolTip.text: modelData.path || ""

                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: if (root.viewModel) root.viewModel.selectFile(browserRow.modelData.path || "")
                            onDoubleClicked: if (root.viewModel) root.viewModel.selectFile(browserRow.modelData.path || "")
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 520)
                visible: !root.viewModel || root.viewModel.itemCount === 0
                text: !root.viewModel
                    ? "文件浏览尚未连接。"
                    : root.viewModel.isLoading
                        ? "正在读取所选目录。"
                        : root.viewModel.browserEnabled
                            ? "选择目录后，这里会显示第一层支持的音频文件。"
                            : "预览模式不会读取真实目录。"
                color: root.theme.muted
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Text {
                    text: root.viewModel && root.viewModel.hasSelection
                        ? "当前选中：" + root.viewModel.selectedFilePath
                        : "当前选中：无"
                    color: root.viewModel && root.viewModel.hasSelection ? root.theme.textPrimary : root.theme.muted
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeSmall
                    Layout.fillWidth: true
                    elide: Text.ElideMiddle
                    maximumLineCount: 1
                }
                Text {
                    text: root.fileSession && root.fileSession.hasCurrentFile
                        ? "工作区已载入：" + root.fileSession.currentFilePath
                        : "工作区已载入：无"
                    color: root.fileSession && root.fileSession.hasCurrentFile ? root.theme.accent : root.theme.muted
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeSmall
                    Layout.fillWidth: true
                    elide: Text.ElideMiddle
                    maximumLineCount: 1
                }
            }

            BrowserButton {
                text: "载入选中文件"
                enabled: root.viewModel && root.viewModel.canLoadSelected
                onClicked: root.viewModel.loadSelected()
            }
        }

        Text {
            visible: root.viewModel && root.viewModel.status.length > 0
            text: root.viewModel ? root.viewModel.status : ""
            color: root.viewModel && root.viewModel.error.length > 0
                ? root.theme.error
                : root.theme.textSecondary
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeTiny
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    component HeaderText: Text {
        color: root.theme.textSecondary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeTiny
        font.weight: root.typography.weightMedium
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    component RowText: Text {
        color: root.theme.textSecondary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeTiny
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    component BrowserButton: WorkstationButton {
        theme: root.theme
        typography: root.typography
        tone: "secondary"
    }
}

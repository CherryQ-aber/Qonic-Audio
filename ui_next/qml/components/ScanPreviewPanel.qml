import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel: null

    implicitHeight: scanLayout.implicitHeight + theme.spacing * 2
    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall

    ColumnLayout {
        id: scanLayout

        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    text: "目录扫描预览"
                    color: theme.textPrimary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeMedium
                    font.weight: typography.weightBold
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Text {
                    text: root.viewModel && root.viewModel.scanPreviewEnabled
                        ? "扫描只读取目录；加入任务队列和开始转换都必须由用户显式操作。"
                        : "当前模式下无法读取真实目录；不会自动扫描或产生输出。"
                    color: root.viewModel && root.viewModel.scanPreviewEnabled
                        ? theme.accent
                        : theme.warning
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.viewModel && root.viewModel.scanPreviewEnabled
                    ? "扫描已启用"
                    : "预览模式"
                tone: root.viewModel && root.viewModel.scanPreviewEnabled
                    ? "accent"
                    : "muted"
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.viewModel && root.viewModel.isScanning
                    ? "扫描中"
                    : "空闲"
                tone: root.viewModel && root.viewModel.isScanning
                    ? "warning"
                    : "muted"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            PathDisplay {
                Layout.fillWidth: true
                label: "当前目录"
                value: root.viewModel && root.viewModel.folderPath !== ""
                    ? root.viewModel.folderPath
                    : "未选择"
            }

            PreviewButton {
                text: "选择目录"
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.chooseFolderForPreview()
                    }
                }
            }

            PreviewButton {
                text: "扫描"
                loading: root.viewModel && root.viewModel.isScanning
                iconName: "refresh"
                enabled: root.viewModel && !root.viewModel.isScanning
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.scanSelectedFolderPreview()
                    }
                }
            }

            PreviewButton {
                text: "取消扫描"
                enabled: root.viewModel && root.viewModel.isScanning
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.cancelScan()
                    }
                }
            }

            PreviewButton {
                text: "清除预览"
                iconName: "clear"
                enabled: root.viewModel && (root.viewModel.itemCount > 0 || root.viewModel.folderPath !== "")
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.clearPreview()
                    }
                }
            }

            CheckBox {
                id: recursiveCheck
                checked: root.viewModel ? root.viewModel.recursive : false
                text: "递归"
                enabled: root.viewModel && !root.viewModel.isScanning
                onToggled: {
                    if (root.viewModel) {
                        root.viewModel.setRecursivePreview(checked)
                    }
                }

                contentItem: Text {
                    text: recursiveCheck.text
                    color: recursiveCheck.enabled ? theme.textSecondary : theme.muted
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: recursiveCheck.indicator.width + recursiveCheck.spacing
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width >= 720 ? 7 : width >= 520 ? 4 : 2
            columnSpacing: 6
            rowSpacing: 6

            SummaryTile { title: "总条目"; value: root.viewModel ? root.viewModel.totalEntries : 0 }
            SummaryTile { title: "已扫描文件"; value: root.viewModel ? root.viewModel.scannedFiles : 0 }
            SummaryTile { title: "支持音频"; value: root.viewModel ? root.viewModel.supportedCount : 0; tone: "accent" }
            SummaryTile { title: "不支持"; value: root.viewModel ? root.viewModel.unsupportedCount : 0 }
            SummaryTile { title: ".lrc"; value: root.viewModel ? root.viewModel.lrcCount : 0 }
            SummaryTile {
                title: "最近扫描"
                value: root.viewModel ? root.viewModel.lastScanTime : "尚未扫描"
                compactValue: true
            }
            SummaryTile {
                title: "上限"
                value: root.viewModel && root.viewModel.tooManyFiles
                    ? "已截断"
                    : ((root.viewModel ? root.viewModel.maxFiles : 1000) + " 文件")
                tone: root.viewModel && root.viewModel.tooManyFiles ? "warning" : "muted"
                compactValue: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.viewModel && root.viewModel.itemCount > 0 ? 156 : 88
            color: theme.surface
            border.color: theme.border
            radius: theme.radiusSmall
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    HeaderText { text: "文件名"; Layout.fillWidth: true }
                    HeaderText { text: "扩展名"; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignHCenter }
                    HeaderText { text: "格式"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignHCenter }
                    HeaderText { text: "大小"; Layout.preferredWidth: 86; horizontalAlignment: Text.AlignRight }
                    HeaderText { text: "支持"; Layout.preferredWidth: 64; horizontalAlignment: Text.AlignHCenter }
                    HeaderText { text: "队列状态"; Layout.preferredWidth: 88; horizontalAlignment: Text.AlignHCenter }
                    HeaderText { text: "扫描状态 / 错误"; Layout.preferredWidth: 158 }
                }

                ListView {
                    id: previewList

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 4
                    model: root.viewModel ? root.viewModel.items : []

                    delegate: ScanRowDelegate {
                        width: previewList.width
                        theme: root.theme
                        typography: root.typography
                        itemData: modelData
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 520)
                visible: !root.viewModel || root.viewModel.itemCount === 0
                text: root.viewModel && root.viewModel.scanPreviewEnabled
                    ? "当前没有扫描结果。请选择目录后执行扫描。"
                    : "目录扫描当前不可用；预览模式不会读取真实目录。"
                color: theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: !root.viewModel || !root.viewModel.hasSelectedAudio
                    ? "请选择一个音频文件。"
                    : "已选择 " + root.viewModel.selectedCount + " 个候选 · 可载入工作区、单文件转换或加入任务队列。"
                color: root.viewModel && root.viewModel.hasSelectedAudio
                    ? theme.accent
                    : theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                width: Math.max(220, parent.width - 360)
                elide: Text.ElideMiddle
                maximumLineCount: 1
            }

            PreviewButton {
                text: "载入工作区"
                enabled: root.viewModel && root.viewModel.hasSelectedAudio
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.loadSelectedFileIntoWorkspace()
                    }
                }
            }

            PreviewButton {
                text: "作为单文件转换输入"
                enabled: root.viewModel && root.viewModel.canUseSelectedFileForConvert
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.sendSelectedFileToSingleConvert()
                    }
                }
            }

            PreviewButton {
                text: "加入已选项"
                enabled: root.viewModel && root.viewModel.canAddSelectedToQueue
                disabledReason: root.viewModel && !root.viewModel.queueMutationEnabled
                    ? "当前不可用；加入任务不会自动转换。"
                    : "请先选择可转换的扫描结果。"
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.addSelectedToQueue()
                    }
                }
            }

            PreviewButton {
                text: "全部可转换项入队"
                enabled: root.viewModel && root.viewModel.canAddAllToQueue
                disabledReason: root.viewModel && !root.viewModel.queueMutationEnabled
                    ? "当前不可用；加入任务不会自动转换。"
                    : "当前没有可加入的扫描结果。"
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.addAllToQueue()
                    }
                }
            }
        }

        Text {
            text: root.viewModel && root.viewModel.queueMutationEnabled
                ? "加入队列只创建任务参数快照；输出格式与目录的后续修改不会改变已创建任务。"
                : "当前模式下无法加入队列；扫描本身不会自动转换。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            maximumLineCount: 2
        }

        Text {
            visible: root.viewModel && root.viewModel.statusMessage !== ""
            text: root.viewModel ? root.viewModel.statusMessage : ""
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTiny
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    component PathDisplay: Rectangle {
        property string label: ""
        property string value: ""

        implicitHeight: 30
        color: theme.surface
        border.color: theme.border
        radius: theme.radiusSmall

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 9
            anchors.rightMargin: 9
            spacing: 8

            Text {
                text: label
                color: theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
            }

            Text {
                id: pathValue
                text: value
                color: value === "未选择" ? theme.muted : theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                Layout.fillWidth: true
                elide: Text.ElideMiddle
                maximumLineCount: 1

                ToolTip.visible: mouseArea.containsMouse && value !== "未选择"
                ToolTip.text: value

                MouseArea {
                    id: mouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
        }
    }

    component SummaryTile: Rectangle {
        property string title: ""
        property var value: 0
        property string tone: "muted"
        property bool compactValue: false

        Layout.fillWidth: true
        implicitHeight: 45
        color: theme.surface
        border.color: tone === "warning" ? theme.warning : theme.border
        radius: theme.radiusSmall

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 7
            spacing: 2

            Text {
                text: title
                color: theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                text: value
                color: tone === "accent" ? theme.accent : tone === "warning" ? theme.warning : theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: compactValue ? typography.sizeTiny : typography.sizeBody
                font.weight: typography.weightBold
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }

    component HeaderText: Text {
        color: theme.textSecondary
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeTiny
        font.weight: typography.weightMedium
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    component PreviewButton: WorkstationButton {
        theme: root.theme
        typography: root.typography
        tone: "secondary"
    }

    component ScanRowDelegate: Rectangle {
        property QtObject theme
        property QtObject typography
        property var itemData: ({})

        implicitHeight: 30
        property bool selected: root.viewModel
            && root.viewModel.selectedFilePaths.indexOf(itemData.path || "") >= 0
        property bool hovered: rowMouse.containsMouse

        color: selected
            ? theme.selectedBackground
            : hovered ? theme.hoverBackground
            : itemData.is_supported_audio
            ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.08)
            : itemData.is_lrc
                ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.07)
                : theme.panel
        border.color: selected ? theme.selectedIndicator : theme.borderNormal
        radius: theme.radiusSmall

        Behavior on color { ColorAnimation { duration: theme.durationFast } }
        Behavior on border.color { ColorAnimation { duration: theme.durationFast } }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 9
            anchors.rightMargin: 9
            spacing: 8

            RowText {
                text: itemData.filename || "-"
                Layout.fillWidth: true
                elide: Text.ElideMiddle
            }
            RowText { text: itemData.extension || "-"; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignHCenter }
            RowText { text: itemData.format_label || "-"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignHCenter }
            RowText { text: itemData.size_text || "-"; Layout.preferredWidth: 86; horizontalAlignment: Text.AlignRight }
            RowText {
                text: itemData.is_supported_audio ? "是" : "否"
                color: itemData.is_supported_audio ? theme.accent : theme.muted
                Layout.preferredWidth: 64
                horizontalAlignment: Text.AlignHCenter
            }
            RowText {
                text: itemData.queue_status || "未入队"
                color: itemData.can_add_to_queue ? theme.accent : theme.muted
                Layout.preferredWidth: 88
                horizontalAlignment: Text.AlignHCenter
            }
            RowText {
                text: itemData.skip_reason || itemData.scan_status || "候选"
                color: itemData.skip_reason ? theme.textSecondary : theme.accent
                Layout.preferredWidth: 158
            }
        }

        ToolTip.visible: rowMouse.containsMouse && itemData.path
        ToolTip.text: itemData.path || ""

        MouseArea {
            id: rowMouse

            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                if (root.viewModel) {
                    root.viewModel.selectAudioCandidate(itemData.path || "")
                }
            }
        }
    }

    component RowText: Text {
        color: theme.textSecondary
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeTiny
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }
}

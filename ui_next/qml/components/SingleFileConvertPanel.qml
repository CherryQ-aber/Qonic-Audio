import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel: null

    property bool showResultDetails: root.viewModel
        && (root.viewModel.lastResultPath !== ""
            || root.viewModel.lastErrorCode !== ""
            || root.viewModel.finalizationStrategy !== "")
    property bool showAdvancedDetails: false

    property var targetFormatOptions: {
        var formats = root.viewModel ? root.viewModel.outputFormatOptions : ["flac"]
        var options = []
        for (var index = 0; index < formats.length; index += 1) {
            options.push({"value": formats[index], "label": formats[index].toUpperCase()})
        }
        return options
    }

    function userResultMessage() {
        if (!root.viewModel) {
            return "尚未选择输入文件和全新输出路径。"
        }
        if (root.viewModel.lastErrorCode === "OUTPUT_CONFLICT") {
            return "目标路径已被其他程序创建。为避免覆盖，本次输出未写入该路径。"
        }
        if (root.viewModel.lastErrorCode === "PERMISSION_DENIED") {
            return "转换失败：无法写入目标目录。"
        }
        if (root.viewModel.convertStatus === "转换成功") {
            return "转换完成，输出文件已安全生成，未覆盖已有文件。"
        }
        if (root.viewModel.convertStatus === "转换失败" || root.viewModel.convertStatus === "校验失败") {
            return "转换失败：输出路径不可用或输入文件无法处理。"
        }
        return root.viewModel.progressText
    }

    implicitHeight: convertLayout.implicitHeight + theme.spacing * 2
    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall

    ColumnLayout {
        id: convertLayout

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
                    text: "单文件转换试点"
                    color: theme.textPrimary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeMedium
                    font.weight: typography.weightBold
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Text {
                    text: root.viewModel && root.viewModel.singleFileConvertEnabled
                        ? "受控单文件转换已启用：仅可转换到全新输出路径。"
                        : "预览模式：单文件转换不会生成文件。"
                    color: root.viewModel && root.viewModel.singleFileConvertEnabled
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
                label: root.viewModel && root.viewModel.singleFileConvertEnabled
                    ? "单文件转换已启用"
                    : "预览模式"
                tone: root.viewModel && root.viewModel.singleFileConvertEnabled
                    ? "accent"
                    : "warning"
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.viewModel ? root.viewModel.convertStatus : "未开始"
                tone: root.viewModel && root.viewModel.convertStatus === "转换成功"
                    ? "success"
                    : root.viewModel && (root.viewModel.convertStatus === "转换失败" || root.viewModel.convertStatus === "校验失败")
                        ? "danger"
                        : root.viewModel && root.viewModel.isConverting
                            ? "warning"
                            : "muted"
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width >= 700 ? 2 : 1
            columnSpacing: theme.spacing
            rowSpacing: 8

            PathField {
                Layout.fillWidth: true
                theme: root.theme
                typography: root.typography
                label: "输入文件"
                path: root.viewModel && root.viewModel.inputPath !== ""
                    ? root.viewModel.inputPath
                    : ""
                helperText: root.viewModel && root.viewModel.inputPath !== ""
                    ? root.viewModel.inputFileName + " · 输入来源：" + root.viewModel.inputSourceLabel
                    : "请选择一个普通音频文件；NCM 暂不支持。"
                browseEnabled: root.viewModel && !root.viewModel.isConverting
                onBrowseRequested: {
                    if (root.viewModel) {
                        root.viewModel.chooseInputFile()
                    }
                }
            }

            PathField {
                Layout.fillWidth: true
                theme: root.theme
                typography: root.typography
                label: "输出路径"
                path: root.viewModel && root.viewModel.outputPath !== ""
                    ? root.viewModel.outputPath
                    : ""
                helperText: "必须选择不存在的新文件；已存在会被拒绝。"
                browseEnabled: root.viewModel && !root.viewModel.isConverting
                onBrowseRequested: {
                    if (root.viewModel) {
                        root.viewModel.chooseOutputFile()
                    }
                }
            }
        }

        Text {
            text: root.viewModel && root.viewModel.inputPath !== ""
                ? "输入来源：" + root.viewModel.inputSourceLabel
                : "输入来源：未选择"
            color: root.viewModel && root.viewModel.inputSourceLabel === "目录扫描预览"
                ? theme.accent
                : theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTiny
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width >= 700 ? 4 : 2
            columnSpacing: 8
            rowSpacing: 8

            SummaryTile { title: "输入格式"; value: root.viewModel ? root.viewModel.inputFormat : "未选择" }
            SummaryTile { title: "源文件大小"; value: root.viewModel ? root.viewModel.sourceSizeText : "-" }
            SummaryTile { title: "输出大小"; value: root.viewModel ? root.viewModel.outputSizeText : "-" }
            SummaryTile { title: "耗时"; value: root.viewModel ? (root.viewModel.durationMs + " ms") : "0 ms" }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            FormatSelector {
                id: targetCombo

                Layout.preferredWidth: 110
                theme: root.theme
                typography: root.typography
                enabled: root.viewModel && !root.viewModel.isConverting
                options: root.targetFormatOptions
                value: root.viewModel ? root.viewModel.targetFormat : "flac"
                onFormatSelected: function(value) {
                    if (root.viewModel) {
                        root.viewModel.setTargetFormat(value)
                    }
                }
            }

            ActionButton {
                text: "使用当前文件"
                enabled: fileSessionViewModel && fileSessionViewModel.hasCurrentFile
                    && root.viewModel && root.viewModel.singleFileConvertEnabled
                    && !root.viewModel.isConverting
                onClicked: {
                    if (root.viewModel && fileSessionViewModel) {
                        root.viewModel.setInputFileFromCurrentSession(fileSessionViewModel.currentFilePath)
                    }
                }
            }

            ActionButton {
                text: "开始单文件转换"
                loading: root.viewModel && root.viewModel.isConverting
                enabled: root.viewModel && !root.viewModel.isConverting
                highlightedAction: true
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.startSingleFileConvert()
                    }
                }
            }

            ActionButton {
                text: "清除状态"
                iconName: "clear"
                enabled: root.viewModel && !root.viewModel.isConverting
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.clearSingleConvertState()
                    }
                }
            }

            ActionButton {
                text: "打开输出位置"
                iconName: "open"
                enabled: root.viewModel && (root.viewModel.lastResultPath !== "" || root.viewModel.outputPath !== "")
                onClicked: {
                    if (root.viewModel) {
                        root.viewModel.openOutputLocation()
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: root.showResultDetails && root.showAdvancedDetails ? 102
                : root.showResultDetails ? 76 : 60
            color: theme.surface
            border.color: theme.border
            radius: theme.radiusSmall

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 2

                Text {
                    text: root.userResultMessage()
                    color: theme.textSecondary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Text {
                    text: "当前只允许单文件转换到全新输出路径。禁止覆盖；若转换期间出现同名文件，操作将失败。"
                    color: theme.muted
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeTiny
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                Button {
                    visible: root.showResultDetails
                    text: root.showAdvancedDetails ? "收起详细信息" : "查看详细信息"
                    implicitHeight: 22
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeTiny
                    onClicked: root.showAdvancedDetails = !root.showAdvancedDetails

                    contentItem: Text {
                        text: parent.text
                        color: theme.accent
                        font: parent.font
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Item {}
                }

                Text {
                    visible: root.showResultDetails && root.showAdvancedDetails
                    text: "错误代码：" + (root.viewModel.lastErrorCode || "无")
                        + " · 落位策略：" + (root.viewModel.finalizationStrategy || "未记录")
                        + " · 临时文件清理：" + (root.viewModel.tempCleanupOk ? "完成" : "需检查")
                    color: root.viewModel && (!root.viewModel.tempCleanupOk || root.viewModel.lastErrorCode === "OUTPUT_CONFLICT")
                        ? theme.warning : theme.muted
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeTiny
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            DisabledAction { text: "队列请使用上方扫描结果" }
            DisabledAction { text: "批量请使用上方转换控制" }
            DisabledAction { text: "输出路径需手动选择" }
            DisabledAction { text: "覆盖已有文件" }
            DisabledAction { text: "歌词修改请导出副本" }
            DisabledAction { text: "封面修改请导出副本" }
            DisabledAction { text: "信息修改请导出副本" }
            DisabledAction { text: "监听请使用上方控制" }

        }

        Text {
            text: root.viewModel && root.viewModel.singleFileConvertEnabled
                ? "单文件转换在此选择全新输出路径；批量转换请先在上方扫描结果中入队，再点击“开始转换”。"
                : "预览模式下不会生成文件。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            maximumLineCount: 2
        }
    }

    component SummaryTile: Rectangle {
        property string title: ""
        property string value: ""

        Layout.fillWidth: true
        implicitHeight: 42
        color: theme.surface
        border.color: theme.border
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
                text: value || "-"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                font.weight: typography.weightBold
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }

    component ActionButton: WorkstationButton {
        property bool highlightedAction: false

        theme: root.theme
        typography: root.typography
        tone: highlightedAction ? "primary" : "secondary"
    }

    component DisabledAction: WorkstationButton {
        enabled: false
        implicitHeight: theme.controlHeightSmall
        Layout.preferredWidth: 94
        theme: root.theme
        typography: root.typography
        disabledReason: "此区域仅用于单文件转换；请使用上方的扫描、队列和转换控制。"
    }
}

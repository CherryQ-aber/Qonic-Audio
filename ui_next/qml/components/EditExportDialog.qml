import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Dialog {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var editSession: null
    property bool metadataSelected: false
    property bool lyricsSelected: false
    property bool coverSelected: false
    readonly property var preflight: root.editSession
        ? root.editSession.unifiedExportPreflight(root.metadataSelected, root.lyricsSelected, root.coverSelected)
        : ({ "selected_operations": [], "required_capabilities": [], "missing_capabilities": [], "supported_modules": [], "unsupported_modules": [], "can_export": false })
    readonly property bool hasSelection: root.preflight.selected_operations.length > 0
    readonly property bool hasMissingCapability: root.preflight.missing_capabilities.length > 0
    readonly property bool hasUnsupportedModule: root.preflight.unsupported_modules.length > 0

    objectName: "unifiedEditExportDialog"
    modal: true
    visible: root.editSession && root.editSession.unifiedExportDialogOpen
    closePolicy: Popup.NoAutoClose
    anchors.centerIn: parent
    width: Math.min(720, parent.width - root.theme.spacing * 4)
    title: "导出编辑副本"
    standardButtons: Dialog.NoButton

    function resetSelections() {
        if (!root.editSession)
            return
        root.metadataSelected = root.editSession.unifiedExportDefaultModule === "metadata" && root.editSession.dirty
        root.lyricsSelected = root.editSession.unifiedExportDefaultModule === "lyrics" && root.editSession.lyricsDirty
        root.coverSelected = root.editSession.unifiedExportDefaultModule === "cover" && root.editSession.coverDirty
    }

    onVisibleChanged: {
        if (visible)
            resetSelections()
    }

    contentItem: ScrollView {
        clip: true
        contentWidth: availableWidth
        implicitHeight: Math.min(620, exportContent.implicitHeight + root.theme.spacing * 2)

        ColumnLayout {
            id: exportContent
            width: parent.availableWidth
            spacing: root.theme.spacing

            Text {
                text: "本次操作只会生成新的音频副本，不会修改或覆盖当前源文件。"
                color: root.theme.warning
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeBody
                font.weight: root.typography.weightMedium
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            GroupBox {
                title: "源文件"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: 5
                    Text { text: root.editSession ? "文件：" + root.editSession.sourcePath.split("/").pop().split("\\").pop() : "文件：-"; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; elide: Text.ElideRight }
                    Text { text: root.editSession ? "路径：" + root.editSession.sourcePath : "路径：-"; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true; elide: Text.ElideMiddle }
                    Text { text: root.editSession && root.editSession.sourcePath.length > 0 ? "格式：" + root.editSession.sourcePath.split(".").pop().toUpperCase() + " · 源文件不会被修改" : "格式：-"; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true }
                }
            }

            GroupBox {
                title: "导出范围"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: 5
                    CheckBox {
                        id: metadataBox
                        visible: root.editSession && root.editSession.dirty
                        enabled: !root.editSession || !root.editSession.unifiedExporting
                        checked: root.metadataSelected
                        text: "Metadata 修改（" + (root.editSession ? root.editSession.changedFieldCount : 0) + " 项：" + (root.editSession ? root.editSession.changedFields.join("、") : "") + "）"
                        onToggled: root.metadataSelected = checked
                    }
                    CheckBox {
                        id: lyricsBox
                        visible: root.editSession && root.editSession.lyricsDirty
                        enabled: !root.editSession || !root.editSession.unifiedExporting
                        checked: root.lyricsSelected
                        text: "Lyrics 修改（来源：" + (root.editSession ? root.editSession.lyricsSource : "-") + "；" + (root.editSession ? root.editSession.lyricsLineCount : 0) + " 行；" + (root.editSession && root.editSession.lyricsHasTimestamps ? "含时间戳" : "无时间戳") + "）"
                        onToggled: root.lyricsSelected = checked
                    }
                    CheckBox {
                        id: coverBox
                        visible: root.editSession && root.editSession.coverDirty
                        enabled: !root.editSession || !root.editSession.unifiedExporting
                        checked: root.coverSelected
                        text: "Cover 修改（" + (root.editSession ? root.editSession.coverAction : "-") + "；" + (root.editSession ? root.editSession.draftCoverMime : "-") + "；" + (root.editSession ? root.editSession.draftCoverDimensions : "-") + "）"
                        onToggled: root.coverSelected = checked
                    }
                    Text { visible: !root.hasSelection; text: "请至少选择一个存在修改的模块。"; color: root.theme.error; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true }
                    RowLayout {
                        Layout.fillWidth: true
                        Button { text: "仅当前模块"; enabled: root.editSession && !root.editSession.unifiedExporting; onClicked: root.resetSelections() }
                        Button { text: "导出全部修改"; enabled: root.editSession && !root.editSession.unifiedExporting; onClicked: { root.metadataSelected = root.editSession.dirty; root.lyricsSelected = root.editSession.lyricsDirty; root.coverSelected = root.editSession.coverDirty } }
                    }
                }
            }

            GroupBox {
                title: "导出检查"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: 4
                    CapabilityLine { label: "文件信息修改"; needed: root.metadataSelected; allowed: root.editSession && root.editSession.metadataWriteEnabled }
                    CapabilityLine { label: "歌词修改"; needed: root.lyricsSelected; allowed: root.editSession && root.editSession.lyricsWriteEnabled }
                    CapabilityLine { label: "封面修改"; needed: root.coverSelected; allowed: root.editSession && root.editSession.coverWriteEnabled }
                    Text { visible: root.hasMissingCapability; text: "所选内容当前无法导出。请取消相应项目后重试；系统不会创建临时副本或修改原文件。"; color: root.theme.error; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { visible: root.hasUnsupportedModule; text: "当前格式不支持：" + root.preflight.unsupported_modules.join("、") + "。WAV / AAC 等受限格式不会伪报写入成功。"; color: root.theme.error; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }

            GroupBox {
                title: "输出设置"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        TextField {
                            id: outputPathField
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            enabled: root.editSession && !root.editSession.unifiedExporting
                            placeholderText: "手动选择全新的音频输出路径"
                            text: root.editSession ? root.editSession.unifiedExportOutputPath : ""
                            onTextEdited: if (root.editSession) root.editSession.setUnifiedExportOutputPath(text)
                        }
                        Button { text: "选择路径"; enabled: root.editSession && !root.editSession.unifiedExporting; onClicked: root.editSession.chooseUnifiedExportOutputPath() }
                    }
                    Text { text: root.editSession ? root.editSession.unifiedExportValidationMessage : ""; color: root.editSession && root.editSession.unifiedExportState === "ready" ? root.theme.success : root.theme.warning; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { text: "输出必须是与源文件同扩展名的全新文件；已存在路径、源路径和覆盖操作都会被拒绝。"; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }

            GroupBox {
                visible: root.editSession && root.editSession.unifiedExportMessage.length > 0
                title: "最近导出结果"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: 5
                    Text { text: root.editSession ? root.editSession.unifiedExportMessage : ""; color: root.editSession && root.editSession.unifiedExportResult.success === true ? root.theme.success : root.theme.error; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { text: root.editSession ? "输出：" + (root.editSession.unifiedExportResult.output_path || "-") : ""; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; elide: Text.ElideMiddle }
                    Text { text: root.editSession ? "已应用：" + (root.editSession.unifiedExportResult.applied_operations || []).join("、") + " · " + (root.editSession.unifiedExportResult.finalization_strategy || "-") : ""; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Text { text: root.editSession ? "跳过：" + (root.editSession.unifiedExportResult.skippedModules || []).join("、") + " · 失败：" + (root.editSession.unifiedExportResult.failedModules || []).join("、") : ""; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Text { text: root.editSession && root.editSession.unifiedExportResult.sourceUnchanged === true ? "源文件完整性：未修改" : ""; color: root.theme.success; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true }
                    Text { visible: root.editSession && (root.editSession.unifiedExportResult.warnings || []).length > 0; text: "警告：" + (root.editSession.unifiedExportResult.warnings || []).join("；"); color: root.theme.warning; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { visible: root.editSession && root.editSession.unifiedExportResult.success === true; text: "修改已导出到副本；当前源文件仍未包含这些修改，草稿保持未保存状态。"; color: root.theme.warning; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    RowLayout {
                        Layout.fillWidth: true
                        Button {
                            text: "复制输出路径"
                            enabled: root.editSession && root.editSession.unifiedExportResult.success === true
                            onClicked: root.editSession.copyUnifiedExportOutputPath()
                        }
                        Button {
                            text: "打开输出位置"
                            enabled: root.editSession && root.editSession.unifiedExportResult.success === true
                            onClicked: root.editSession.openUnifiedExportLocation()
                        }
                        Button {
                            text: "载入为当前文件"
                            enabled: root.editSession && root.editSession.canLoadUnifiedExportResult
                            onClicked: root.editSession.loadUnifiedExportResultAsCurrent()
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button {
                    text: "取消导出"
                    visible: root.editSession && root.editSession.unifiedExporting
                    enabled: root.editSession && root.editSession.unifiedExporting
                    onClicked: root.editSession.cancelExport()
                }
                Button { text: "关闭"; enabled: root.editSession && !root.editSession.unifiedExporting; onClicked: root.editSession.closeUnifiedExportDialog() }
                Button { text: root.editSession && root.editSession.unifiedExporting ? "正在导出…" : "导出新音频副本"; enabled: root.editSession && root.hasSelection && !root.hasMissingCapability && !root.hasUnsupportedModule && root.editSession.unifiedExportOutputPath.length > 0 && !root.editSession.unifiedExporting; onClicked: root.editSession.startUnifiedAudioExport(root.metadataSelected, root.lyricsSelected, root.coverSelected) }
            }
        }
    }

    component CapabilityLine: RowLayout {
        property string label: ""
        property bool needed: false
        property bool allowed: false
        Layout.fillWidth: true
        Text { text: parent.label; color: parent.needed ? root.theme.textPrimary : root.theme.muted; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true }
        Text { text: !parent.needed ? "未选择" : parent.allowed ? "已启用" : "缺少"; color: !parent.needed ? root.theme.muted : parent.allowed ? root.theme.success : root.theme.error; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall }
    }
}

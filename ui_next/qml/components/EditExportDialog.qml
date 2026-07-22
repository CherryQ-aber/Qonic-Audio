import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Dialog {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var editSession: null
    property var processingSession: null
    property bool selectAllDraftsOnOpen: false
    property bool metadataSelected: false
    property bool lyricsSelected: false
    property bool coverSelected: false
    property bool processingSelected: false
    readonly property bool lrcTarget: root.editSession
        && root.editSession.unifiedExportTarget === "lrc"
    readonly property var preflight: root.editSession
        ? root.editSession.unifiedExportPreflight(
            root.metadataSelected,
            root.lyricsSelected,
            root.coverSelected,
            root.processingSelected
        )
        : ({ "selected_operations": [], "missing_capabilities": [], "unsupported_modules": [] })
    readonly property bool hasSelection: root.lrcTarget
        ? Boolean(root.editSession && root.editSession.lyricsDirty)
        : root.preflight.selected_operations.length > 0
    readonly property bool hasMissingCapability: root.lrcTarget
        ? Boolean(root.editSession && !root.editSession.lyricsWriteEnabled)
        : root.preflight.missing_capabilities.length > 0
    readonly property bool hasUnsupportedModule: !root.lrcTarget
        && root.preflight.unsupported_modules.length > 0

    objectName: "unifiedEditExportDialog"
    modal: true
    visible: root.editSession && root.editSession.unifiedExportDialogOpen
    closePolicy: Popup.NoAutoClose
    anchors.centerIn: parent
    width: Math.min(760, parent.width - root.theme.spacing * 4)
    title: "导出"
    standardButtons: Dialog.NoButton

    function resetSelections() {
        if (!root.editSession)
            return
        root.metadataSelected = root.editSession.dirty
        root.lyricsSelected = root.editSession.lyricsDirty
        root.coverSelected = root.editSession.coverDirty
        root.processingSelected = root.editSession.processingDirty
    }

    function startExport(overwriteExisting) {
        if (!root.editSession)
            return
        if (root.lrcTarget) {
            root.editSession.startUnifiedLrcExport(overwriteExisting)
            return
        }
        root.editSession.startUnifiedAudioExport(
            root.metadataSelected,
            root.lyricsSelected,
            root.coverSelected,
            root.processingSelected,
            overwriteExisting
        )
    }

    function requestExport() {
        if (!root.editSession)
            return
        if (root.editSession.unifiedExportOverwriteRequired)
            overwriteConfirmDialog.open()
        else
            root.startExport(false)
    }

    onVisibleChanged: {
        if (visible)
            resetSelections()
        else if (overwriteConfirmDialog.visible)
            overwriteConfirmDialog.close()
    }

    contentItem: ScrollView {
        id: exportScroll

        clip: true
        implicitWidth: root.width - root.leftPadding - root.rightPadding
        contentWidth: availableWidth
        implicitHeight: Math.min(660, exportContent.implicitHeight + root.theme.spacing * 2)

        ColumnLayout {
            id: exportContent
            width: exportScroll.availableWidth
            spacing: root.theme.spacing

            Text {
                text: root.selectAllDraftsOnOpen
                    ? "切换文件前会导出全部未保存修改；本次不能只导出部分草稿。"
                    : "所有编辑内容都保留为草稿。默认另存新文件；选择已有文件时会在执行前再次确认。"
                color: root.theme.textSecondary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            GroupBox {
                title: "导出类型"
                Layout.fillWidth: true
                RowLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    Button {
                        text: "音频文件"
                        checkable: true
                        checked: !root.lrcTarget
                        enabled: root.editSession
                            && !root.editSession.unifiedExporting
                            && !root.selectAllDraftsOnOpen
                        onClicked: root.editSession.setUnifiedExportTarget("audio")
                    }
                    Button {
                        text: "LRC 歌词"
                        checkable: true
                        checked: root.lrcTarget
                        visible: root.editSession
                            && root.editSession.lyricsDirty
                            && !root.selectAllDraftsOnOpen
                        enabled: root.editSession
                            && !root.editSession.unifiedExporting
                            && !root.selectAllDraftsOnOpen
                        onClicked: root.editSession.setUnifiedExportTarget("lrc")
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.lrcTarget ? "另存或覆盖 .lrc" : "嵌入所选草稿并生成音频"
                        color: root.theme.muted
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                    }
                }
            }

            GroupBox {
                title: root.lrcTarget ? "导出内容" : "包含的未保存修改"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 5

                    CheckBox {
                        visible: !root.lrcTarget && root.editSession && root.editSession.dirty
                        enabled: root.editSession
                            && !root.editSession.unifiedExporting
                            && !root.selectAllDraftsOnOpen
                        checked: root.metadataSelected
                        text: "文件信息 · " + (root.editSession ? root.editSession.changedFieldCount : 0) + " 项未保存"
                        onToggled: root.metadataSelected = checked
                    }
                    CheckBox {
                        visible: root.editSession && root.editSession.lyricsDirty
                        enabled: !root.lrcTarget
                            && root.editSession
                            && !root.editSession.unifiedExporting
                            && !root.selectAllDraftsOnOpen
                        checked: root.lrcTarget || root.lyricsSelected
                        text: "歌词 · " + (root.editSession ? root.editSession.lyricsLineCount : 0) + " 行未保存"
                        onToggled: if (!root.lrcTarget) root.lyricsSelected = checked
                    }
                    CheckBox {
                        visible: !root.lrcTarget && root.editSession && root.editSession.coverDirty
                        enabled: root.editSession
                            && !root.editSession.unifiedExporting
                            && !root.selectAllDraftsOnOpen
                        checked: root.coverSelected
                        text: "封面 · " + (root.editSession ? root.editSession.coverAction : "") + " 未保存"
                        onToggled: root.coverSelected = checked
                    }
                    CheckBox {
                        visible: !root.lrcTarget && root.editSession && root.editSession.processingDirty
                        enabled: root.editSession
                            && !root.editSession.unifiedExporting
                            && !root.selectAllDraftsOnOpen
                        checked: root.processingSelected
                        text: "音频处理 · " + (root.editSession ? root.editSession.processingSemitone : 0) + " 半音未保存"
                        onToggled: root.processingSelected = checked
                    }
                    Text {
                        visible: !root.hasSelection
                        text: "请至少选择一项未保存修改。"
                        color: root.theme.error
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        Layout.fillWidth: true
                    }
                }
            }

            GroupBox {
                title: "输出位置"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        TextField {
                            id: outputPathField
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            enabled: root.editSession && !root.editSession.unifiedExporting
                            placeholderText: root.lrcTarget
                                ? "选择 .lrc 输出路径"
                                : "选择音频输出路径"
                            text: root.editSession ? root.editSession.unifiedExportOutputPath : ""
                            onTextEdited: if (root.editSession)
                                root.editSession.setUnifiedExportOutputPath(text)
                        }
                        Button {
                            text: "浏览…"
                            enabled: root.editSession && !root.editSession.unifiedExporting
                            onClicked: root.editSession.chooseUnifiedExportOutputPath()
                        }
                    }
                    Text {
                        text: root.editSession ? root.editSession.unifiedExportValidationMessage : ""
                        color: root.editSession && root.editSession.unifiedExportOverwriteRequired
                            ? root.theme.warning
                            : root.editSession && root.editSession.unifiedExportState === "ready"
                                ? root.theme.success : root.theme.textSecondary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: root.editSession && root.editSession.unifiedExportOverwritesSource
                        text: "当前选择的是源音频。确认后将以完整草稿生成替换文件，并在写回验证失败时自动恢复。"
                        color: root.theme.warning
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            Text {
                visible: root.hasMissingCapability || root.hasUnsupportedModule
                text: root.hasMissingCapability
                    ? "当前运行模式缺少所选导出能力。"
                    : "当前格式不支持：" + root.preflight.unsupported_modules.join("、")
                color: root.theme.error
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            GroupBox {
                visible: root.editSession && root.editSession.unifiedExportMessage.length > 0
                title: "导出结果"
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 5
                    Text {
                        text: root.editSession ? root.editSession.unifiedExportMessage : ""
                        color: root.editSession && root.editSession.unifiedExportResult.success === true
                            ? root.theme.success : root.theme.error
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Text {
                        text: root.editSession
                            ? "输出：" + (root.editSession.unifiedExportResult.output_path || "-") : ""
                        color: root.theme.textSecondary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Button {
                            text: "复制路径"
                            enabled: root.editSession && root.editSession.unifiedExportResult.success === true
                            onClicked: root.editSession.copyUnifiedExportOutputPath()
                        }
                        Button {
                            text: "打开位置"
                            enabled: root.editSession && root.editSession.unifiedExportResult.success === true
                            onClicked: root.editSession.openUnifiedExportLocation()
                        }
                        Button {
                            text: "载入为当前文件"
                            visible: !root.lrcTarget
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
                Button {
                    text: "关闭"
                    enabled: root.editSession && !root.editSession.unifiedExporting
                    onClicked: root.editSession.closeUnifiedExportDialog()
                }
                Button {
                    text: root.editSession && root.editSession.unifiedExporting
                        ? "正在导出…"
                        : root.editSession && root.editSession.unifiedExportOverwriteRequired
                            ? "检查并覆盖" : "导出"
                    enabled: root.editSession
                        && root.hasSelection
                        && !root.hasMissingCapability
                        && !root.hasUnsupportedModule
                        && root.editSession.unifiedExportOutputPath.length > 0
                        && root.editSession.unifiedExportState === "ready"
                        && !root.editSession.unifiedExporting
                    onClicked: root.requestExport()
                }
            }
        }
    }

    Dialog {
        id: overwriteConfirmDialog
        objectName: "editExportOverwriteConfirmDialog"
        modal: true
        title: root.editSession && root.editSession.unifiedExportOverwritesSource
            ? "确认覆盖源音频？" : "确认覆盖已有文件？"
        standardButtons: Dialog.NoButton
        closePolicy: Popup.NoAutoClose
        anchors.centerIn: parent
        width: Math.min(500, root.width - root.theme.spacing * 4)

        contentItem: ColumnLayout {
            spacing: root.theme.spacing
            Text {
                text: root.editSession && root.editSession.unifiedExportOverwritesSource
                    ? "你选择了当前源音频。系统会先生成完整替换文件并保留临时回滚副本，验证成功后才完成覆盖。此操作会改变原文件。"
                    : "目标路径已经存在。确认后将替换该文件；如果最终内容验证失败，系统会尝试恢复覆盖前文件。"
                color: root.theme.textPrimary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeBody
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Text {
                text: root.editSession ? root.editSession.unifiedExportOutputPath : ""
                color: root.theme.warning
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                wrapMode: Text.WrapAnywhere
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "返回"; onClicked: overwriteConfirmDialog.close() }
                Button {
                    text: root.editSession && root.editSession.unifiedExportOverwritesSource
                        ? "确认覆盖源文件" : "确认覆盖"
                    onClicked: {
                        overwriteConfirmDialog.close()
                        root.startExport(true)
                    }
                }
            }
        }
    }
}

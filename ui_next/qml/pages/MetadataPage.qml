import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root
    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property var editSession: null
    property int workspaceColumns: pageScroll.width >= 880 ? 3
        : pageScroll.width >= 660 ? 2 : 1

    function requestMetadataExport() {
        if (editSession)
            editSession.openUnifiedExportDialog("metadata")
    }
    function requestCoverExport() {
        if (editSession)
            editSession.openUnifiedExportDialog("cover")
    }

    function pageSafetyMessage() {
        if (editSession && editSession.hasSession)
            return "当前修改仅保存在编辑草稿中，不会立即修改音频文件。导出只会另存新文件。"
        if (metadataViewModel.metadataReadEnabled && coverViewModel.coverReadEnabled)
            return "文件信息与封面读取已启用；选择音频后可在内存草稿中编辑信息与封面。"
        if (coverViewModel.coverReadEnabled)
            return "封面读取已启用；选择音频后可在内存草稿中替换、移除或恢复封面。"
        return metadataViewModel.metadataReadEnabled ? "文件信息可供查看，修改会保存在草稿中。" : "预览模式不会读取真实文件信息。"
    }
    function pageCapabilityLabel() {
        if (editSession && editSession.hasSession) return "编辑草稿已创建"
        if (metadataViewModel.metadataReadEnabled && coverViewModel.coverReadEnabled) return "信息已就绪"
        if (metadataViewModel.metadataReadEnabled) return "文件信息已就绪"
        if (coverViewModel.coverReadEnabled) return "封面预览已就绪"
        return "预览模式"
    }
    function pageHasLiveCapability() { return metadataViewModel.metadataReadEnabled || coverViewModel.coverReadEnabled }

        Flickable {
            id: pageScroll
            objectName: "metadataPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: pageContent.implicitHeight + root.theme.spacing * 2
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ThemeScrollBar { theme: root.theme; policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: pageContent
            objectName: "metadataPageContent"
            width: pageScroll.width
            Layout.minimumWidth: 0
            spacing: root.theme.spacing

            SectionCard {
                objectName: "metadataSafetyCard"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                tone: root.pageHasLiveCapability() ? "normal" : "warning"
                implicitHeight: safetyContent.implicitHeight + root.theme.spacing * 2
                ColumnLayout {
                    id: safetyContent
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: root.theme.spacing
                    spacing: 7
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        StatusBadge { theme: root.theme; typography: root.typography; label: root.pageCapabilityLabel(); tone: root.pageHasLiveCapability() ? "accent" : "muted" }
                        StatusBadge { visible: root.audioPlayer && root.audioPlayer.playerState === "playing"; theme: root.theme; typography: root.typography; label: "当前文件播放中"; tone: "success" }
                    }
                    Text { text: root.pageSafetyMessage(); color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeBody; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Text {
                        objectName: "metadataInlineStatus"
                        text: fileSessionViewModel.currentFilePath === ""
                            ? "尚未导入音频。导入后可查看和编辑文件信息与封面。"
                            : metadataViewModel.statusMessage
                        color: fileSessionViewModel.currentFilePath === ""
                            ? root.theme.warning : root.theme.textSecondary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeSmall
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }
            }

            GridLayout {
                id: metadataSummaryGrid
                objectName: "metadataSummaryGrid"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                columns: root.workspaceColumns
                columnSpacing: root.theme.spacing
                rowSpacing: root.theme.spacing

                CoverDraftEditor {
                    objectName: "metadataCoverEditor"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: root.workspaceColumns === 3
                        ? (metadataSummaryGrid.width - root.theme.spacing * 2) * 0.24
                        : root.workspaceColumns === 2
                            ? (metadataSummaryGrid.width - root.theme.spacing) * 0.31
                            : metadataSummaryGrid.width
                    theme: root.theme
                    typography: root.typography
                    editSession: root.editSession
                    onReplaceRequested: if (root.editSession) root.editSession.chooseReplacementCover()
                    onRemoveRequested: if (root.editSession) root.editSession.removeCoverDraft()
                    onRestoreRequested: if (root.editSession) root.editSession.restoreOriginalCover()
                    onExportRequested: root.requestCoverExport()
                }

                MetadataForm {
                    objectName: "metadataTagSummaryCard"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: root.workspaceColumns === 3
                        ? (metadataSummaryGrid.width - root.theme.spacing * 2) * 0.50
                        : root.workspaceColumns === 2
                            ? (metadataSummaryGrid.width - root.theme.spacing) * 0.69
                            : metadataSummaryGrid.width
                    theme: root.theme
                    typography: root.typography
                    viewModel: metadataViewModel
                    editSession: root.editSession
                }

                InfoPanel {
                    objectName: "metadataBaseInfoCard"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    Layout.columnSpan: root.workspaceColumns === 2 ? 2 : 1
                    Layout.preferredWidth: root.workspaceColumns === 3
                        ? (metadataSummaryGrid.width - root.theme.spacing * 2) * 0.26
                        : metadataSummaryGrid.width
                    title: "技术信息"
                    statusLabel: metadataViewModel.metadataReadEnabled ? "仅查看" : "预览信息"
                    InfoRow { label: "文件名"; value: metadataViewModel.currentFileName }
                    InfoRow { label: "文件路径"; value: metadataViewModel.currentFilePath === "" ? "-" : metadataViewModel.currentFilePath; middleElide: true }
                    InfoRow { label: "文件格式"; value: metadataViewModel.fileFormat }
                    InfoRow { label: "文件大小"; value: metadataViewModel.fileSizeText }
                    InfoRow { label: "时长"; value: metadataViewModel.durationText }
                    InfoRow { label: "采样率"; value: metadataViewModel.sampleRateText }
                    InfoRow { label: "比特率"; value: metadataViewModel.bitRateText }
                    InfoRow { label: "声道"; value: metadataViewModel.channelsText }
                    InfoRow { label: "读取后端"; value: metadataViewModel.readBackend }
                    InfoRow { label: "读取状态"; value: metadataViewModel.readStatus }
                    ReadOnlyButton { label: "打开文件位置"; enabled: fileSessionViewModel.hasCurrentFile; onClicked: fileSessionViewModel.openCurrentFileLocation() }
                }
            }

            SectionCard {
                objectName: "metadataEditActionsCard"
                Layout.fillWidth: true; Layout.minimumWidth: 0
                implicitHeight: editActionsContent.implicitHeight + root.theme.spacing * 2
                ColumnLayout {
                    id: editActionsContent
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: root.theme.spacing
                    spacing: 7
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        ReadOnlyButton { label: "保存草稿"; enabled: !!(root.editSession && root.editSession.hasSession); onClicked: root.editSession.saveDraft() }
                        ReadOnlyButton { label: "恢复原始信息"; enabled: !!(root.editSession && root.editSession.dirty); onClicked: root.editSession.restoreOriginal() }
                        ReadOnlyButton { label: "导出修改（另存新文件）"; enabled: !!(root.editSession && root.editSession.dirty && !root.editSession.anyExporting); onClicked: root.requestMetadataExport() }
                    }
                    Text { text: root.editSession && root.editSession.metadataWriteEnabled ? "导出只会生成您手动选择的新文件，不会覆盖原文件。" : "当前无法导出此草稿；不会创建临时副本或修改原文件。"; color: root.theme.muted; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Text { visible: !!(root.editSession && root.editSession.unifiedExportMessage.length > 0); text: root.editSession ? root.editSession.unifiedExportMessage : ""; color: root.editSession && root.editSession.unifiedExportResult.success === true ? root.theme.success : root.theme.warning; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Text { visible: !!(root.editSession && root.editSession.unifiedExportResult.success === true); text: root.editSession ? "输出路径：" + root.editSession.unifiedExportResult.output_path : ""; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                }
            }
            Item { Layout.minimumHeight: root.theme.spacing }
        }
    }

    component InfoPanel: SectionCard {
        id: panelCard
        property string title: ""
        property string statusLabel: ""
        default property alias content: panelContent.data
        implicitHeight: panelContent.implicitHeight + root.theme.spacing * 2
        ColumnLayout {
            id: panelContent
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: root.theme.spacing + 2
            spacing: 8
            RowLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                Text { text: panelCard.title; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeMedium; font.weight: root.typography.weightBold; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight; maximumLineCount: 1 }
                StatusBadge { visible: panelCard.statusLabel.length > 0; theme: root.theme; typography: root.typography; label: panelCard.statusLabel; tone: "muted" }
            }
        }
    }
    component InfoRow: RowLayout {
        property string label: ""; property string value: ""; property bool middleElide: false
        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 8
        Text { text: parent.label; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.preferredWidth: 70; Layout.minimumWidth: 0; elide: Text.ElideRight; maximumLineCount: 1 }
        Text { id: infoValue; text: parent.value === "" ? "-" : parent.value; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: parent.middleElide ? Text.ElideMiddle : Text.ElideRight; maximumLineCount: 1; ToolTip.visible: infoMouse.containsMouse && parent.value.length > 0; ToolTip.text: parent.value; MouseArea { id: infoMouse; anchors.fill: parent; hoverEnabled: true } }
    }
    component ReadOnlyButton: Button {
        property string label: ""; text: label; implicitWidth: 126; implicitHeight: 30
        font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall
        contentItem: Text { text: parent.text; color: parent.enabled ? root.theme.textPrimary : root.theme.muted; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; maximumLineCount: 1 }
        background: Rectangle { color: parent.enabled ? root.theme.surface : Qt.rgba(root.theme.muted.r, root.theme.muted.g, root.theme.muted.b, 0.08); border.color: parent.enabled ? root.theme.border : Qt.rgba(root.theme.border.r, root.theme.border.g, root.theme.border.b, 0.5); radius: root.theme.radiusSmall }
    }
    component DisabledAction: ReadOnlyButton { enabled: false }
}

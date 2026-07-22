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

    function resetPageScrollIfContentFits() {
        if (pageScroll.contentHeight <= pageScroll.height + 0.5
                && pageScroll.contentY !== 0) {
            pageScroll.contentY = 0
        }
    }

    Flickable {
        id: pageScroll
        objectName: "metadataPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: Math.max(height, pageContent.implicitHeight)
        boundsBehavior: Flickable.StopAtBounds
        onHeightChanged: root.resetPageScrollIfContentFits()
        onContentHeightChanged: root.resetPageScrollIfContentFits()
        ScrollBar.vertical: ThemeScrollBar {
            theme: root.theme
            policy: ScrollBar.AsNeeded
            visible: size < 0.999
        }

        ColumnLayout {
            id: pageContent
            objectName: "metadataPageContent"
            width: pageScroll.width
            Layout.minimumWidth: 0
            spacing: root.theme.spacing

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

        }
    }

    component InfoPanel: SectionCard {
        id: panelCard
        theme: root.theme
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

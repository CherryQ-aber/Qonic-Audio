import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

SectionCard {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var editSession: null

    signal replaceRequested()
    signal removeRequested()
    signal restoreRequested()

    objectName: "coverDraftEditor"
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    implicitHeight: content.implicitHeight + theme.spacing * 2

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.theme.spacing
        spacing: root.theme.spacing

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "封面编辑"
                color: root.theme.textPrimary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeMedium
                font.weight: root.typography.weightBold
                Layout.fillWidth: true
            }
            StatusBadge {
                visible: root.editSession && root.editSession.coverDirty
                theme: root.theme
                typography: root.typography
                label: "未保存"
                tone: "warning"
            }
        }

        PreviewPane {
            objectName: "coverEffectivePreview"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            title: root.editSession && root.editSession.coverAction === "replace"
                ? "当前有效封面 · 替换草稿"
                : root.editSession && root.editSession.coverAction === "remove"
                    ? "当前有效封面 · 待移除"
                    : "当前有效封面"
            source: root.editSession && root.editSession.coverAction !== "remove"
                ? root.editSession.draftCoverPreviewUrl : ""
            emptyText: !root.editSession || !root.editSession.hasSession
                ? "选择音频后显示封面"
                : root.editSession.coverEditState === "error"
                    || root.editSession.coverEditState === "failed"
                    ? "封面读取失败"
                    : root.editSession.coverAction === "remove"
                        ? "导出后将移除封面"
                        : "当前文件没有封面"
            mime: root.editSession ? root.editSession.draftCoverMime : ""
            dimensions: root.editSession ? root.editSession.draftCoverDimensions : "-"
            byteSize: root.editSession ? root.editSession.draftCoverSize : 0
        }

        Text {
            visible: root.editSession && root.editSession.coverValidationError.length > 0
            text: root.editSession ? root.editSession.coverValidationError : ""
            color: root.theme.error
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8
            DraftButton {
                text: "选择替换封面"
                enabled: root.editSession && root.editSession.hasSession && !root.editSession.anyExporting
                onClicked: root.replaceRequested()
            }
            DraftButton {
                text: "移除封面"
                enabled: root.editSession && root.editSession.hasOriginalCover && !root.editSession.anyExporting
                onClicked: root.removeRequested()
            }
            DraftButton {
                text: "恢复原始"
                enabled: root.editSession && root.editSession.coverDirty && !root.editSession.anyExporting
                onClicked: root.restoreRequested()
            }
        }
    }

    component PreviewPane: Rectangle {
        id: previewPane
        property string title: ""
        property string source: ""
        property string emptyText: ""
        property string mime: ""
        property string dimensions: "-"
        property int byteSize: 0

        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitHeight: paneContent.implicitHeight + root.theme.spacing * 2
        color: root.theme.surface
        border.color: root.theme.border
        radius: root.theme.radiusSmall

        ColumnLayout {
            id: paneContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: root.theme.spacing
            spacing: 6
            Text { text: previewPane.title; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; font.weight: root.typography.weightBold; Layout.fillWidth: true }
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(196, Math.max(132, previewPane.width - root.theme.spacing * 2))
                Layout.preferredHeight: Layout.preferredWidth
                color: root.theme.panel
                border.color: root.theme.border
                clip: true
                Image { anchors.fill: parent; anchors.margins: 7; source: previewPane.source; fillMode: Image.PreserveAspectFit; visible: previewPane.source !== "" }
                Text { anchors.centerIn: parent; width: parent.width - 20; text: previewPane.emptyText; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; visible: previewPane.source === "" }
            }
            Text { text: "格式：" + (previewPane.mime.length > 0 ? previewPane.mime : "-"); color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true; elide: Text.ElideRight }
            Text { text: "尺寸：" + previewPane.dimensions + " · " + (previewPane.byteSize > 0 ? previewPane.byteSize + " B" : "-"); color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true; elide: Text.ElideRight }
        }
    }

    component DraftButton: Button {
        implicitHeight: 31
        implicitWidth: 142
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
        contentItem: Text { text: parent.text; color: parent.enabled ? root.theme.textPrimary : root.theme.muted; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; maximumLineCount: 1 }
        background: Rectangle { color: parent.enabled ? root.theme.surface : Qt.rgba(root.theme.surface.r, root.theme.surface.g, root.theme.surface.b, 0.55); border.color: parent.enabled ? root.theme.border : Qt.rgba(root.theme.border.r, root.theme.border.g, root.theme.border.b, 0.55); radius: root.theme.radiusSmall }
    }
}

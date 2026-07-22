import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var viewModel: null
    property var editSession: null

    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall
    implicitHeight: metadataContent.implicitHeight + theme.spacing * 2

    function draftValue(fieldName) {
        if (!editSession || !editSession.hasSession)
            return ""
        var value = editSession.draftMetadata[fieldName]
        return value === undefined || value === null ? "" : String(value)
    }

    function originalValue(fieldName) {
        if (!editSession || !editSession.hasSession)
            return ""
        var value = editSession.originalMetadata[fieldName]
        return value === undefined || value === null ? "" : String(value)
    }

    ColumnLayout {
        id: metadataContent
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: theme.spacingSm

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Text {
                text: "文件信息编辑（草稿）"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: !root.editSession || !root.editSession.hasSession
                    ? "等待读取"
                    : root.editSession.dirty
                        ? "已修改 " + root.editSession.changedFieldCount + " 项"
                        : "无修改"
                tone: root.editSession && root.editSession.dirty ? "warning" : "muted"
            }
        }

        Text {
            text: root.editSession && root.editSession.hasSession
                ? "原始信息来自只读读取；下列输入框是当前草稿。每项下方显示原始值。"
                : "需要先启用 metadata_read 并读取当前工作区文件，才能创建编辑草稿。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Text {
            text: "基础信息"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightBold
            Layout.fillWidth: true
        }

        GridLayout {
            id: basicGrid
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            columns: width >= 420 ? 2 : 1
            columnSpacing: theme.spacing
            rowSpacing: 10

            MetadataField { Layout.fillWidth: true; label: "标题"; fieldName: "title" }
            MetadataField { Layout.fillWidth: true; label: "艺术家"; fieldName: "artist" }
            MetadataField { Layout.fillWidth: true; label: "专辑"; fieldName: "album" }
            MetadataField { Layout.fillWidth: true; label: "年份"; fieldName: "date" }
            MetadataField { Layout.fillWidth: true; label: "流派"; fieldName: "genre" }
        }

        Text {
            text: "扩展信息"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightBold
            Layout.fillWidth: true
        }

        GridLayout {
            id: extendedGrid
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            columns: width >= 420 ? 2 : 1
            columnSpacing: theme.spacing
            rowSpacing: 10

            MetadataField { Layout.fillWidth: true; label: "专辑艺术家"; fieldName: "albumartist" }
            MetadataField { Layout.fillWidth: true; label: "轨道号"; fieldName: "tracknumber" }
            MetadataField { Layout.fillWidth: true; label: "Disc Number"; fieldName: "discnumber" }
            MetadataField { Layout.fillWidth: true; label: "评论"; fieldName: "comment" }
            UnsupportedField {
                Layout.fillWidth: true
                label: "Composer"
                message: "当前受控元数据写入后端尚未支持 Composer；本阶段不会伪装为可导出字段。"
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        Text {
            text: root.editSession ? root.editSession.statusMessage : "编辑草稿未初始化"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }

    component MetadataField: ColumnLayout {
        property string label: ""
        property string fieldName: ""

        spacing: 5
        Layout.minimumWidth: 0

        Text {
            text: parent.label
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        TextField {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: 34
            text: root.draftValue(parent.fieldName)
            color: theme.textPrimary
            selectedTextColor: theme.textInverse
            selectionColor: theme.selectedIndicator
            placeholderText: "留空"
            placeholderTextColor: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeBody
            enabled: root.editSession && root.editSession.canEdit
            background: Rectangle {
                color: theme.inputBackground
                border.color: parent.activeFocus ? theme.focusRing : theme.borderNormal
                border.width: parent.activeFocus ? 2 : 1
                radius: theme.radiusSmall
            }
            onEditingFinished: {
                if (root.editSession)
                    root.editSession.updateField(parent.fieldName, text)
            }
        }

        Text {
            text: "原始：" + (root.originalValue(parent.fieldName) || "（空）")
            color: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
            ToolTip.visible: originalHover.containsMouse
            ToolTip.text: root.originalValue(parent.fieldName)
            MouseArea { id: originalHover; anchors.fill: parent; hoverEnabled: true }
        }
    }

    component UnsupportedField: ColumnLayout {
        property string label: ""
        property string message: ""
        spacing: 5
        Layout.minimumWidth: 0

        Text {
            text: parent.label
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
        }
        Text {
            text: parent.message
            color: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var editorSession

    color: theme.panel
    border.color: theme.border
    border.width: 1
    radius: theme.radiusSmall
    implicitHeight: exportContent.implicitHeight + (theme.spacing + 2) * 2

    ColumnLayout {
        id: exportContent
        anchors.fill: parent
        anchors.margins: theme.spacing + 2
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "导出结果"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: editorSession ? editorSession.exportState : "未导出"
                tone: editorSession && editorSession.isExporting
                    ? "warning"
                    : editorSession && editorSession.hasLastExport
                      ? "success"
                      : "muted"
            }
        }

        Text {
            text: editorSession && editorSession.lastExportPath ? editorSession.lastExportPath : "最近导出结果：无"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8

            ResultButton {
                text: "打开导出位置（占位）"
                enabled: editorSession && editorSession.hasLastExport
                onClicked: editorSession.openLastExportLocationMock()
            }

            ResultButton {
                text: "加载模拟结果为当前文件"
                enabled: editorSession && editorSession.hasLastExport
                onClicked: editorSession.loadExportResultAsCurrentMock()
            }
        }
    }

    component ResultButton: Button {
        width: 220
        implicitWidth: width
        implicitHeight: 30
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall

        contentItem: Text {
            text: parent.text
            color: parent.enabled ? theme.textPrimary : theme.muted
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font: parent.font
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        background: Rectangle {
            color: parent.enabled ? theme.surface : Qt.rgba(theme.muted.r, theme.muted.g, theme.muted.b, 0.08)
            border.color: parent.enabled ? theme.border : Qt.rgba(theme.border.r, theme.border.g, theme.border.b, 0.5)
            radius: theme.radiusSmall
        }
    }
}

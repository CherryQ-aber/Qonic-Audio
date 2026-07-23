import QtQuick
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
    implicitHeight: previewContent.implicitHeight + (theme.spacing + 2) * 2

    ColumnLayout {
        id: previewContent
        anchors.fill: parent
        anchors.margins: theme.spacing + 2
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "模拟试听状态"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
            }

                StatusBadge {
                    theme: root.theme
                    typography: root.typography
                    label: editorSession ? editorSession.previewState : "未生成试听"
                    tone: editorSession && editorSession.isPreviewGenerating
                        ? "warning"
                        : editorSession && editorSession.previewState.indexOf("已生成") >= 0
                          ? "success"
                          : "muted"
                }
        }

        Text {
            text: "预览模式：只显示模拟状态，不读取音频，也不生成试听缓存。"
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Text {
            text: editorSession ? editorSession.previewVersionLabel : "当前试听版本：未生成"
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text {
            text: editorSession ? "播放源：" + editorSession.currentPlaySourceLabel : "播放源：未加载"
            color: theme.muted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTiny
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }
}

import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string currentFilePath: ""
    property string currentLyricsPath: ""
    property string source: "未读取"
    property string status: "未读取"
    property string syncStatus: "未读取"
    property int lineCount: 0
    property bool hasTimestamps: false
    property bool isMemoryPreview: false
    property bool isMockPreview: false
    property string detectedFields: "无"
    property string readBackend: "未调用"
    property string encoding: "-"

    implicitHeight: sourceContent.implicitHeight + theme.spacing * 2
    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall

    ColumnLayout {
        id: sourceContent
        anchors.fill: parent
        anchors.margins: theme.spacing
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacing

            Text {
                text: "歌词来源摘要"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.preferredWidth: 126
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                text: root.currentFilePath === "" ? "当前文件：未选择" : "当前文件：" + root.currentFilePath
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                Layout.fillWidth: true
                elide: Text.ElideMiddle
                maximumLineCount: 1
            }
        }

        Text {
            text: root.currentLyricsPath === ""
                ? "当前 .lrc：未选择"
                : "当前 .lrc：" + root.currentLyricsPath
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

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: "来源：" + root.source
                tone: root.source === "无歌词" || root.source === "未读取" ? "muted" : "accent"
                width: implicitWidth
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: "状态：" + root.status
                tone: root.status === "无歌词" || root.status === "未读取" ? "muted" : "success"
                width: implicitWidth
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.hasTimestamps ? "时间戳：有" : "时间戳：无"
                tone: root.hasTimestamps ? "success" : "muted"
                width: implicitWidth
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: "行数：" + root.lineCount
                tone: root.lineCount > 0 ? "accent" : "muted"
                width: implicitWidth
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.isMemoryPreview ? "内存预览：是" : "内存预览：否"
                tone: root.isMemoryPreview ? "accent" : "muted"
                width: implicitWidth
            }

            StatusBadge {
                theme: root.theme
                typography: root.typography
                label: root.isMockPreview ? "预览信息" : "只读来源"
                tone: root.isMockPreview ? "muted" : "accent"
                width: implicitWidth
            }

        }

        Flow {
            id: technicalDetails
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "检测字段：" + root.detectedFields
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                width: Math.min(implicitWidth, technicalDetails.width)
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                text: "编码：" + root.encoding
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                width: Math.min(implicitWidth, technicalDetails.width)
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                text: "后端：" + root.readBackend
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                width: Math.min(implicitWidth, technicalDetails.width)
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }
}

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string moduleName: ""
    property string moduleDescription: ""
    property string runtimeLabel: "预览模式"
    property string enabledFeatures: "无"
    property string safetySummary: ""
    property string actionHint: ""
    property var fileSession: null
    property var audioPlayer: null
    property var editSession: null
    property var processingSession: null

    implicitWidth: theme.inspectorWidth
    color: theme.panel
    border.color: theme.border
    border.width: 1

    ScrollView {
        id: inspectorScroll
        objectName: "rightInspectorScroll"

        anchors.fill: parent
        clip: true
        padding: theme.spacing
        // Do not bind to availableWidth here: that value itself changes after
        // the vertical scrollbar appears, which can leave a narrow inspector
        // with a horizontal overflow loop.
        contentWidth: Math.max(0, width - leftPadding - rightPadding
            - inspectorVerticalScrollBar.width)
        contentHeight: inspectorContent.implicitHeight

        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: ThemeScrollBar {
            id: inspectorVerticalScrollBar
            theme: root.theme
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: inspectorContent
            objectName: "rightInspectorContent"

            width: inspectorScroll.availableWidth
            spacing: theme.spacing

            Text {
                text: "检查器"
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                font.weight: typography.weightMedium
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: moduleContent.implicitHeight + theme.spacing * 2
                color: theme.surface
                border.color: theme.border
                radius: theme.radiusSmall

                ColumnLayout {
                    id: moduleContent

                    anchors.fill: parent
                    anchors.margins: theme.spacing
                    spacing: 4

                    Text {
                        text: root.moduleName
                        color: theme.textPrimary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeMedium
                        font.weight: typography.weightBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        text: root.moduleDescription
                        color: theme.textSecondary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        Layout.fillWidth: true
                    }
                }
            }

            InspectorSection {
                theme: root.theme
                typography: root.typography
                title: "运行状态"
                lines: [
                    "当前状态：" + root.runtimeLabel,
                    "可用功能：" + root.enabledFeatures,
                    "操作提示：" + root.actionHint,
                    "安全保护：" + root.safetySummary
                ]
            }

            InspectorSection {
                theme: root.theme; typography: root.typography; title: "Pitch Shift 处理会话"
                lines: !root.processingSession || !root.processingSession.hasSource ? ["当前无处理会话"] : [
                    "参数：" + (root.processingSession.semitone > 0 ? "+" : "") + root.processingSession.semitone + " 半音",
                    "播放源：" + (root.processingSession.currentPlaybackSource === "preview" ? "Pitch Shift 试听缓存" : "原音频"),
                    "缓存：" + (root.processingSession.previewValid ? "已就绪" : root.processingSession.processingState),
                    "最近输出：" + (root.processingSession.exportPath || "尚未导出"),
                    "编辑草稿：" + (root.editSession && root.editSession.hasUnsavedDrafts ? "存在，Pitch Shift 不会应用" : "无"),
                    "原文件被修改：否"
                ]
            }

            InspectorSection {
                theme: root.theme
                typography: root.typography
                title: "选中文件"
                lines: !root.fileSession || !root.fileSession.hasCurrentFile
                    ? ["当前无工作区文件"]
                    : [
                        "文件：" + root.fileSession.currentFileName,
                        "来源：" + root.fileSession.currentFileSourceLabel,
                        "格式：" + root.fileSession.currentFileExtension.toUpperCase(),
                        "Metadata：" + root.fileSession.metadataState,
                        "歌词：" + root.fileSession.lyricsState,
                        "封面：" + root.fileSession.coverState,
                        "播放：" + (root.audioPlayer ? root.audioPlayer.playerState : "未加载"),
                        root.audioPlayer && root.audioPlayer.playerState === "playing"
                            ? "进度：" + root.audioPlayer.position + " / " + root.audioPlayer.duration + " ms" : "",
                        root.fileSession.currentFilePath
                    ]
            }

            InspectorSection {
                theme: root.theme
                typography: root.typography
                title: "输出与处理"
                lines: ["输出格式：未绑定", "处理队列：未绑定", "系统对话框仍保留在原生层"]
            }

            InspectorSection {
                theme: root.theme
                typography: root.typography
                title: "歌词草稿"
                lines: !root.editSession || !root.editSession.hasSession
                    ? ["当前无歌词草稿"]
                    : [
                        "来源：" + root.editSession.lyricsSource,
                        "时间戳：" + (root.editSession.lyricsHasTimestamps ? "有" : "无"),
                        "行数：" + root.editSession.lyricsLineCount,
                        "草稿：" + (root.editSession.lyricsDirty ? "有未导出修改" : "未修改"),
                        root.editSession.lastLyricsExportMessage
                    ]
            }

            InspectorSection {
                theme: root.theme
                typography: root.typography
                title: "封面草稿"
                lines: !root.editSession || !root.editSession.hasSession
                    ? ["当前无封面草稿"]
                    : [
                        "原始封面：" + (root.editSession.hasOriginalCover ? "存在" : "无"),
                        "当前动作：" + root.editSession.coverAction,
                        "格式：" + (root.editSession.draftCoverMime || "-"),
                        "尺寸：" + root.editSession.draftCoverDimensions,
                        "草稿：" + (root.editSession.coverDirty ? "有未导出修改" : "未修改"),
                        root.editSession.lastCoverExportMessage
                    ]
            }

            InspectorSection {
                objectName: "unifiedEditExportResultSection"
                theme: root.theme
                typography: root.typography
                title: "最近编辑导出"
                lines: !root.editSession || root.editSession.unifiedExportMessage.length === 0
                    ? ["本次运行尚未导出编辑副本"]
                    : [
                        "结果：" + (root.editSession.unifiedExportResult.success === true ? "成功" : "失败"),
                        "模块：" + (root.editSession.unifiedExportResult.applied_operations || []).join("、"),
                        "输出：" + (root.editSession.unifiedExportResult.output_path || "-"),
                        "时间：" + root.editSession.unifiedExportTimestamp,
                        root.editSession.unifiedExportMessage
                    ]
            }

            InspectorSection {
                theme: root.theme
                typography: root.typography
                title: "后续用途"
                lines: ["当前文件信息", "输出设置摘要", "歌词摘要", "封面摘要"]
            }

            Item {
                Layout.minimumHeight: 1
                Layout.fillHeight: true
            }
        }
    }

    component InspectorSection: Rectangle {
        property QtObject theme
        property QtObject typography
        property string title: ""
        property var lines: []

        Layout.fillWidth: true
        implicitHeight: sectionLayout.implicitHeight + theme.spacing * 2
        color: theme.surface
        border.color: theme.border
        radius: theme.radiusSmall

        ColumnLayout {
            id: sectionLayout
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: theme.spacing
            spacing: 7

            Text {
                text: title
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeBody
                font.weight: typography.weightMedium
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Repeater {
                model: lines

                delegate: Text {
                    required property string modelData

                    text: modelData
                    color: theme.textSecondary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                }
            }
        }
    }
}

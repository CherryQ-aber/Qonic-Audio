import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root
    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var processingSession
    color: theme.panel; border.color: theme.border; border.width: 1; radius: theme.radiusSmall
    implicitHeight: pitchContent.implicitHeight + (theme.spacing + 4) * 2
    function pitchText(v) { return v === 0 ? "原调 0 半音" : (v > 0 ? "+" : "") + v + " 半音" }
    function stateText(state) {
        const labels = {
            "validating_request": "正在校验请求",
            "preparing_workspace": "正在准备试听工作区",
            "starting_process": "正在启动 FFmpeg",
            "rendering": "正在生成试听缓存",
            "waiting_process_exit": "正在等待 FFmpeg 退出",
            "validating_preview": "正在验证试听文件",
            "loading_player_source": "正在加载试听源",
            "preview_ready": "试听缓存已就绪",
            "playing_preview": "正在播放试听",
            "cancelled": "已取消",
            "error": "处理失败",
            "preview_required": "设置已变更，等待试听",
            "ready": "等待试听",
            "original_playing": "正在使用原音频",
            "exporting": "正在导出正式文件",
            "success": "导出完成"
        }
        return labels[state] || state || "未生成"
    }

    ColumnLayout {
        id: pitchContent
        anchors.fill: parent
        anchors.margins: theme.spacing + 4
        spacing: theme.spacing

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Text {
                text: "升降调工作区"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeLarge
                font.weight: typography.weightBold
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            StatusBadge {
                visible: root.processingSession && root.processingSession.processingDirty
                theme: root.theme
                typography: root.typography
                label: "未保存"
                tone: "warning"
            }
        }

        GridLayout {
            id: pitchWorkspace
            objectName: "pitchWorkspaceGrid"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            columns: root.width >= 700 ? 2 : 1
            columnSpacing: theme.spacing
            rowSpacing: theme.spacing

            WorkspacePane {
                objectName: "pitchParametersPane"
                title: "Pitch 参数"

                ThemedSlider {
                    theme: root.theme
                    Layout.fillWidth: true
                    from: -12
                    to: 12
                    stepSize: 1
                    snapMode: Slider.SnapAlways
                    enabled: root.processingSession && root.processingSession.hasSource
                        && !root.processingSession.isBusy
                    value: root.processingSession ? root.processingSession.semitone : 0
                    onMoved: root.processingSession.setSemitone(value)
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    StepButton {
                        text: "-1 半音"
                        enabled: root.processingSession && root.processingSession.hasSource
                            && !root.processingSession.isBusy
                        onClicked: root.processingSession.setSemitone(root.processingSession.semitone - 1)
                    }
                    StepButton {
                        text: "恢复原始"
                        enabled: root.processingSession && root.processingSession.processingDirty
                            && !root.processingSession.isBusy
                        onClicked: root.processingSession.restoreOriginalProcessing()
                    }
                    StepButton {
                        text: "+1 半音"
                        enabled: root.processingSession && root.processingSession.hasSource
                            && !root.processingSession.isBusy
                        onClicked: root.processingSession.setSemitone(root.processingSession.semitone + 1)
                    }
                }
                StatusLine {
                    label: "当前参数"
                    value: root.processingSession
                        ? root.pitchText(root.processingSession.semitone) : "原调 0 半音"
                }
                Text {
                    text: "范围 -12～+12 半音，步进 1；0 半音直接返回原音频。"
                    color: theme.textSecondary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }

            WorkspacePane {
                objectName: "pitchPreviewPane"
                title: "试听状态与控制"

                StatusLine {
                    label: "当前播放源"
                    value: !root.processingSession ? "未加载"
                        : root.processingSession.currentPlaybackSource === "preview"
                            ? "Pitch Shift 试听（"
                                + root.pitchText(root.processingSession.semitone) + "）"
                            : "原音频"
                }
                StatusLine {
                    label: "试听缓存"
                    middleElide: true
                    value: root.processingSession
                        ? root.processingSession.previewValid
                            ? (root.processingSession.previewCacheHit
                                ? "已验证缓存命中 · " : "")
                                + root.stateText(root.processingSession.processingState)
                                + " · " + root.processingSession.previewPathSummary
                            : root.stateText(root.processingSession.processingState)
                        : "未生成"
                }
                StatusLine {
                    label: "处理阶段"
                    value: root.processingSession
                        ? root.processingSession.progressDetail : "等待请求"
                }
                ProgressBar {
                    from: 0
                    to: 100
                    value: root.processingSession ? root.processingSession.progress : 0
                    indeterminate: root.processingSession && root.processingSession.isBusy && root.processingSession.progress <= 0
                    Layout.fillWidth: true
                }
                Text {
                    visible: root.processingSession
                        && root.processingSession.errorMessage.length > 0
                    text: root.processingSession ? root.processingSession.errorMessage : ""
                    color: theme.error
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Action {
                        text: "试听当前设置"
                        accent: true
                        enabled: root.processingSession
                            && root.processingSession.hasSource
                            && !root.processingSession.isBusy
                            && root.processingSession.audioProcessingEnabled
                            && root.processingSession.audioPlaybackEnabled
                        onClicked: root.processingSession.previewCurrentSetting()
                    }
                    Action {
                        text: "取消生成"
                        enabled: root.processingSession && root.processingSession.isBusy
                        onClicked: root.processingSession.cancelProcessing()
                    }
                    Action {
                        text: "播放试听"
                        enabled: root.processingSession
                            && root.processingSession.previewValid
                            && !root.processingSession.isBusy
                            && root.processingSession.audioPlaybackEnabled
                        onClicked: root.processingSession.playPreview()
                    }
                    Action {
                        text: "返回原音频"
                        enabled: root.processingSession
                            && root.processingSession.hasSource
                            && !root.processingSession.isBusy
                            && root.processingSession.audioPlaybackEnabled
                        onClicked: root.processingSession.returnToOriginal()
                    }
                    Action {
                        text: "清理试听缓存"
                        enabled: root.processingSession
                            && root.processingSession.previewPath.length > 0
                            && !root.processingSession.isBusy
                        onClicked: root.processingSession.cleanPreviewCache()
                    }
                }
            }

        }
    }

    component WorkspacePane: Rectangle {
        id: pane
        property string title: ""
        default property alias content: paneContent.data

        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.alignment: Qt.AlignTop
        implicitHeight: paneContent.implicitHeight + theme.spacing * 2
        color: theme.surface
        border.color: theme.border
        radius: theme.radiusSmall

        ColumnLayout {
            id: paneContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: theme.spacing
            spacing: 8
            Text {
                text: pane.title
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }

    component StatusLine: ColumnLayout {
        property string label: ""
        property string value: ""
        property bool middleElide: false
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 3
        Text {
            text: parent.label
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeTiny
            Layout.fillWidth: true
        }
        Text {
            id: statusValue
            text: parent.value
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            elide: parent.middleElide ? Text.ElideMiddle : Text.ElideRight
            maximumLineCount: 1
            ToolTip.visible: statusHover.containsMouse && statusValue.truncated
            ToolTip.text: parent.value
            MouseArea {
                id: statusHover
                anchors.fill: parent
                hoverEnabled: true
            }
        }
    }

    component StepButton: WorkstationButton {
        width: 104
        implicitHeight: 32
        theme: root.theme
        typography: root.typography
        tone: "secondary"
    }
    component Action: WorkstationButton {
        property bool accent: false
        width: 126
        implicitHeight: 32
        theme: root.theme
        typography: root.typography
        tone: accent ? "primary" : "secondary"
    }
}

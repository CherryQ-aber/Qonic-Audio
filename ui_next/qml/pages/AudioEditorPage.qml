import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var fileSession: null
    property var fileBrowser: null
    property var audioPlayer
    property var editSession: null
    property var processingSession: null

    Flickable {
        id: pageScroll
        objectName: "audioEditorPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: pageContent.implicitHeight + root.theme.spacing * 2
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ThemeScrollBar {
            theme: root.theme
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: pageContent
            objectName: "audioEditorPageContent"
            width: pageScroll.width
            Layout.minimumWidth: 0
            spacing: root.theme.spacing

            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: safetyRow.implicitHeight + root.theme.spacing * 2
                color: Qt.rgba(root.theme.warning.r, root.theme.warning.g, root.theme.warning.b, 0.12)
                border.color: Qt.rgba(root.theme.warning.r, root.theme.warning.g, root.theme.warning.b, 0.58)
                radius: root.theme.radiusSmall

                RowLayout {
                    id: safetyRow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: root.theme.spacing
                    spacing: root.theme.spacing

                    StatusBadge {
                        theme: root.theme
                        typography: root.typography
                        label: root.audioPlayer && root.audioPlayer.audioPlaybackEnabled
                            ? "音频编辑 · 可以播放"
                            : "音频编辑 · 仅安全预览"
                        tone: root.audioPlayer && root.audioPlayer.audioPlaybackEnabled ? "accent" : "warning"
                    }

                    Text {
                        text: root.audioPlayer && root.audioPlayer.audioPlaybackEnabled
                            ? "可播放音频、生成 Pitch Shift 试听并导出新文件；不会覆盖或修改原音频。"
                            : "预览模式不会播放、处理、缓存或导出真实音频。"
                        color: root.theme.textPrimary
                        font.family: root.typography.fontFamily
                        font.pixelSize: root.typography.sizeBody
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }
            }

            CurrentFileBar {
                objectName: "audioEditorCurrentFileCard"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
                fileSession: root.fileSession
                editSession: root.editSession
                audioPlayer: root.audioPlayer
                processingSession: root.processingSession
            }

            EditorFileBrowser {
                objectName: "audioEditorFileBrowser"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
                viewModel: root.fileBrowser
                fileSession: root.fileSession
            }

            PlayerBar {
                objectName: "audioEditorPlayerCard"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
            }

            WaveformPlaceholder {
                objectName: "audioEditorWaveformCard"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
            }

            Rectangle {
                objectName: "audioEditorTabsCard"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: tabs.implicitHeight + root.theme.spacing * 2
                color: root.theme.panel
                border.color: root.theme.border
                radius: root.theme.radiusSmall

                Flow {
                    id: tabs
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: root.theme.spacing
                    spacing: 8

                    TabPill { text: "音频内容处理"; selected: true }
                    TabPill { text: "文件信息整理"; muted: true }
                    TabPill { text: "歌词"; muted: true }
                }
            }

            AudioProcessingPage {
                objectName: "audioEditorProcessingStack"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
                processingSession: root.processingSession
            }

            Item { Layout.minimumHeight: root.theme.spacing }
        }
    }

    DropArea {
        id: workspaceDropArea
        objectName: "audioEditorDropArea"
        anchors.fill: parent
        z: 20
        onEntered: function(drag) {
            drag.accepted = !!root.fileSession
        }
        onDropped: function(drop) {
            if (root.fileSession)
                root.fileSession.handleDroppedUrls(drop.urls)
        }
    }

    Rectangle {
        anchors.fill: parent
        z: 21
        visible: workspaceDropArea.containsDrag
        color: Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, 0.12)
        border.color: root.theme.accent
        border.width: 1
        radius: root.theme.radiusSmall

        Text {
            anchors.centerIn: parent
            width: Math.min(parent.width - root.theme.spacing * 4, 520)
            text: "拖入一个音频文件，或拖入音频与同名 .lrc\n一次不会自动选择多个文件，也不会自动播放。"
            color: root.theme.textPrimary
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeMedium
            font.weight: root.typography.weightBold
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
    }

    component TabPill: Rectangle {
        property alias text: label.text
        property bool selected: false
        property bool muted: false

        implicitWidth: selected ? 132 : 112
        implicitHeight: 28
        radius: root.theme.radiusSmall
        color: selected ? Qt.rgba(root.theme.accent.r, root.theme.accent.g, root.theme.accent.b, 0.16) : "transparent"
        border.color: selected ? root.theme.accent : root.theme.border
        border.width: selected ? 1 : 0

        Text {
            id: label
            anchors.centerIn: parent
            width: parent.width - 12
            color: parent.selected ? root.theme.textPrimary : (parent.muted ? root.theme.muted : root.theme.textSecondary)
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeSmall
            font.weight: parent.selected ? root.typography.weightMedium : root.typography.weightRegular
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }
}

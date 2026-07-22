import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var lines: []
    property int mockCurrentLine: -1
    property int currentLineIndex: -1
    property bool followCurrentLine: true
    readonly property int activeLineIndex: currentLineIndex >= 0
        ? currentLineIndex : mockCurrentLine

    signal followCurrentLineRequested(bool enabled)

    function followActiveLine() {
        if (!followCurrentLine
                || activeLineIndex < 0
                || activeLineIndex >= lyricsPreviewListView.count) {
            return
        }
        lyricsPreviewListView.positionViewAtIndex(
            activeLineIndex,
            ListView.Center
        )
    }

    onActiveLineIndexChanged: Qt.callLater(root.followActiveLine)
    onFollowCurrentLineChanged: if (followCurrentLine)
        Qt.callLater(root.followActiveLine)
    onLinesChanged: Qt.callLater(root.followActiveLine)

    color: theme.panel
    border.color: theme.border
    radius: theme.radiusSmall

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacing + 4
        spacing: theme.spacing

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "歌词滚动预览"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                Layout.fillWidth: true
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            WorkstationButton {
                id: followLyricsButton
                objectName: "lyricsFollowToggle"
                implicitWidth: 126
                implicitHeight: 28
                theme: root.theme
                typography: root.typography
                selectedState: root.followCurrentLine
                text: root.followCurrentLine ? "跟随滚动：开" : "跟随滚动：关"
                enabled: root.lines && root.lines.length > 0
                onClicked: root.followCurrentLineRequested(
                    !root.followCurrentLine
                )
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: lyricsPreviewListView
                objectName: "lyricsPreviewListView"
                anchors.fill: parent
                anchors.rightMargin: lyricsPreviewVerticalScrollBar.width + 4
                clip: true
                spacing: 6
                model: root.lines
                visible: root.lines && root.lines.length > 0
                boundsBehavior: Flickable.StopAtBounds

                ScrollBar.vertical: ThemeScrollBar {
                    id: lyricsPreviewVerticalScrollBar
                    objectName: "lyricsPreviewVerticalScrollBar"
                    parent: lyricsPreviewListView.parent
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 2
                    z: 2
                    theme: root.theme
                    policy: ScrollBar.AlwaysOn
                }

                delegate: Rectangle {
                    required property var modelData
                    required property int index

                    width: ListView.view.width
                    implicitHeight: Math.max(52, lyricColumn.implicitHeight + 14)
                    color: index === root.activeLineIndex
                        ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.16)
                        : modelData.hasTimestamp
                          ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.08)
                          : theme.surface
                    border.color: index === root.activeLineIndex
                        ? theme.warning
                        : modelData.hasTimestamp
                          ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.36)
                          : theme.border
                    radius: theme.radiusSmall

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 10

                        Text {
                            text: "#" + modelData.index
                            color: theme.muted
                            font.family: "Consolas"
                            font.pixelSize: typography.sizeTiny
                            Layout.preferredWidth: 34
                        }

                        Text {
                            text: modelData.hasTimestamp ? modelData.time : "--:--.--"
                            color: modelData.hasTimestamp ? theme.accent : theme.muted
                            font.family: "Consolas"
                            font.pixelSize: typography.sizeTiny
                            font.weight: typography.weightMedium
                            Layout.preferredWidth: 62
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        ColumnLayout {
                            id: lyricColumn
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: modelData.text === "" ? "空行" : modelData.text
                                color: theme.textPrimary
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeSmall
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                            }

                            Text {
                                text: "翻译：" + (modelData.translation === "" ? "—" : modelData.translation)
                                color: theme.muted
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeTiny
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, 560)
                visible: !root.lines || root.lines.length === 0
                text: "当前没有可滚动预览的歌词。可导入 .lrc，或在当前歌词中输入带时间戳的内容。"
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeBody
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }
    }
}

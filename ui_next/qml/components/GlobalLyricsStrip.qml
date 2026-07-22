import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "globalLyricsStrip"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var lyricsSync: null
    property bool compactMode: false

    readonly property string primaryText: {
        if (!lyricsSync)
            return ""
        var lyric = lyricsSync.currentLineText.length > 0
            ? lyricsSync.currentLineText : lyricsSync.nextLineText
        var translation = lyricsSync.currentLineText.length > 0
            ? lyricsSync.currentLineTranslation
            : lyricsSync.nextLineTranslation
        return lyric + (translation.length > 0 ? "  ·  " + translation : "")
    }

    implicitHeight: compactMode ? 26 : 30
    color: Qt.rgba(
        theme.accent.r,
        theme.accent.g,
        theme.accent.b,
        0.07
    )
    border.color: Qt.rgba(
        theme.accent.r,
        theme.accent.g,
        theme.accent.b,
        0.30
    )
    border.width: 1
    radius: theme.radiusSmall

    onPrimaryTextChanged: lineFade.restart()

    Item {
        anchors.fill: parent
        anchors.leftMargin: root.theme.spacingSm
        anchors.rightMargin: root.theme.spacingSm

        RowLayout {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.theme.spacingSm

            Text {
                text: "歌词"
                color: root.theme.accent
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeTiny
                font.weight: root.typography.weightBold
            }

            Text {
                text: root.lyricsSync && root.lyricsSync.currentLineIndex >= 0
                    ? root.lyricsSync.currentLineTime : "等待"
                color: root.theme.textSecondary
                font.family: "Consolas"
                font.pixelSize: root.typography.sizeTiny
                Layout.preferredWidth: 58
            }
        }

        Text {
            id: nextLyricText
            objectName: "globalLyricsNextLine"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: root.width >= 980
                && root.lyricsSync
                && root.lyricsSync.nextLineText.length > 0
            width: Math.min(320, root.width * 0.20)
            text: root.lyricsSync
                ? "下一句  " + root.lyricsSync.nextLineText : ""
            color: root.theme.textMuted
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeTiny
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text {
            id: currentLyricText
            objectName: "globalLyricsCurrentLine"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(
                180,
                Math.min(
                    900,
                    root.width - (nextLyricText.visible ? 580 : 260)
                )
            )
            text: root.primaryText
            color: root.theme.textPrimary
            font.family: root.typography.fontFamily
            font.pixelSize: root.compactMode
                ? root.typography.sizeSmall : root.typography.sizeBody
            font.weight: root.typography.weightMedium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    SequentialAnimation {
        id: lineFade
        NumberAnimation {
            target: currentLyricText
            property: "opacity"
            to: 0.45
            duration: root.theme.durationFast
        }
        NumberAnimation {
            target: currentLyricText
            property: "opacity"
            to: 1
            duration: root.theme.durationNormal
        }
    }
}

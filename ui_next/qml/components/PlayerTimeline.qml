import QtQuick
import QtQuick.Layouts

import "../theme"

RowLayout {
    id: root
    objectName: "globalPlayerTimeline"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false

    spacing: root.theme.spacingSm
    implicitHeight: root.compactMode ? 28 : 32

    function formatTime(milliseconds) {
        var seconds = Math.max(0, Math.floor(milliseconds / 1000))
        var minutes = Math.floor(seconds / 60)
        var remainder = seconds % 60
        return minutes + ":" + (remainder < 10 ? "0" : "") + remainder
    }

    Text {
        Layout.preferredWidth: 46
        text: root.audioPlayer
            ? root.formatTime(root.audioPlayer.position)
            : "0:00"
        color: root.theme.textPrimary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
        horizontalAlignment: Text.AlignRight
    }

    ThemedSlider {
        id: progressSlider
        objectName: "globalPlayerProgressSlider"

        property bool seekPending: false
        property real pendingPosition: 0

        theme: root.theme
        Layout.fillWidth: true
        Layout.minimumWidth: 120
        enabled: root.audioPlayer
            && root.audioPlayer.backendInitialized
            && root.audioPlayer.hasPlaybackSource
            && root.audioPlayer.duration > 0
            && !root.audioPlayer.mediaOperationBusy
        from: 0
        to: root.audioPlayer ? Math.max(1, root.audioPlayer.duration) : 1
        Accessible.name: "播放进度"
        Accessible.description: root.audioPlayer
            ? root.formatTime(root.audioPlayer.position)
                + " / " + root.formatTime(root.audioPlayer.duration)
            : "0:00 / 0:00"

        onMoved: pendingPosition = value
        onPressedChanged: {
            if (pressed) {
                seekPending = true
                pendingPosition = value
            } else if (seekPending) {
                seekPending = false
                if (root.audioPlayer)
                    root.audioPlayer.seek(pendingPosition)
            }
        }

        Binding {
            target: progressSlider
            property: "value"
            value: root.audioPlayer ? root.audioPlayer.position : 0
            when: !progressSlider.pressed
            restoreMode: Binding.RestoreBindingOrValue
        }
    }

    Text {
        Layout.preferredWidth: 46
        text: root.audioPlayer
            ? root.formatTime(root.audioPlayer.duration)
            : "0:00"
        color: root.theme.textSecondary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
    }
}

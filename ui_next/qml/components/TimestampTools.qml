import QtQuick
import QtQuick.Layouts

import "../theme"

RowLayout {
    id: root
    objectName: "globalPlayerTimestampTools"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false
    property bool narrowMode: false

    implicitHeight: root.compactMode ? 28 : 32

    WorkstationButton {
        objectName: "globalPlayerCopyTimestampButton"
        Layout.preferredWidth: root.narrowMode ? 88 : 132
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.narrowMode
            ? "复制时间点"
            : "复制 " + (
                root.audioPlayer
                    ? root.audioPlayer.currentTimestampText
                    : "[00:00.00]"
            )
        enabled: root.audioPlayer && root.audioPlayer.hasPlaybackSource
        disabledReason: "载入播放文件后可复制真实播放位置"
        toolTipText: root.audioPlayer
            ? "复制当前时间点 " + root.audioPlayer.currentTimestampText
            : "复制当前时间点"
        onClicked: root.audioPlayer.copyCurrentTimestamp()
    }
}

import QtQuick
import QtQuick.Layouts

import "../theme"

RowLayout {
    id: root
    objectName: "globalPlayerSeekStepControls"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false
    property bool narrowMode: false

    readonly property int stepSeconds: root.audioPlayer
        ? Math.max(1, Math.round(root.audioPlayer.seekStepMs / 1000))
        : 2
    readonly property bool seekEnabled: root.audioPlayer
        && root.audioPlayer.backendInitialized
        && root.audioPlayer.hasPlaybackSource
        && root.audioPlayer.duration > 0
        && !root.audioPlayer.mediaOperationBusy

    spacing: root.theme.spacingXs
    implicitHeight: root.compactMode ? 30 : 32

    WorkstationButton {
        objectName: "globalPlayerSeekBackwardButton"
        Layout.preferredWidth: root.narrowMode ? 48 : 82
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.narrowMode
            ? "-" + root.stepSeconds + "s"
            : "后退 " + root.stepSeconds + " 秒"
        enabled: root.seekEnabled
        disabledReason: "媒体加载完成后可校对时间点"
        toolTipText: "后退 " + root.stepSeconds + " 秒"
        Accessible.name: "后退 " + root.stepSeconds + " 秒"
        onClicked: root.audioPlayer.seekBackward()
    }

    WorkstationButton {
        objectName: "globalPlayerSeekForwardButton"
        Layout.preferredWidth: root.narrowMode ? 48 : 82
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.narrowMode
            ? "+" + root.stepSeconds + "s"
            : "前进 " + root.stepSeconds + " 秒"
        enabled: root.seekEnabled
        disabledReason: "媒体加载完成后可校对时间点"
        toolTipText: "前进 " + root.stepSeconds + " 秒"
        Accessible.name: "前进 " + root.stepSeconds + " 秒"
        onClicked: root.audioPlayer.seekForward()
    }
}

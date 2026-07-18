import QtQuick
import QtQuick.Layouts

import "../theme"

RowLayout {
    id: root
    objectName: "globalPlayerControls"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false
    property bool narrowMode: false

    spacing: root.theme.spacingXs
    implicitHeight: root.compactMode ? 30 : 32

    function stateLabel(state) {
        if (state === "playing")
            return "播放中"
        if (state === "paused")
            return "已暂停"
        if (state === "ready")
            return "已加载"
        if (state === "loading")
            return "加载中"
        if (state === "finished")
            return "播放结束"
        if (state === "released")
            return "文件操作中"
        if (state === "error")
            return "播放错误"
        if (state === "stopped")
            return "已停止"
        return "未加载"
    }

    WorkstationButton {
        objectName: "globalPlayerPlayButton"
        Layout.preferredWidth: root.narrowMode ? 38 : 62
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.narrowMode ? "▶" : "播放"
        tone: "primary"
        enabled: root.audioPlayer && root.audioPlayer.canPlay
        disabledReason: root.audioPlayer && root.audioPlayer.mediaOperationBusy
            ? "播放器正在为文件操作释放媒体源"
            : "请先载入可播放文件"
        toolTipText: "播放当前全局播放源"
        Accessible.name: "播放"
        onClicked: root.audioPlayer.play()
    }

    WorkstationButton {
        objectName: "globalPlayerPauseButton"
        Layout.preferredWidth: root.narrowMode ? 38 : 62
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.narrowMode ? "Ⅱ" : "暂停"
        enabled: root.audioPlayer
            && root.audioPlayer.playerState === "playing"
            && !root.audioPlayer.mediaOperationBusy
        disabledReason: "当前没有正在播放的音频"
        toolTipText: "暂停当前播放"
        Accessible.name: "暂停"
        onClicked: root.audioPlayer.pause()
    }

    WorkstationButton {
        objectName: "globalPlayerStopButton"
        Layout.preferredWidth: root.narrowMode ? 38 : 62
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.narrowMode ? "■" : "停止"
        enabled: root.audioPlayer
            && root.audioPlayer.hasPlaybackSource
            && root.audioPlayer.playerState !== "empty"
            && root.audioPlayer.playerState !== "released"
            && !root.audioPlayer.mediaOperationBusy
        disabledReason: "当前没有可停止的播放源"
        toolTipText: "停止并返回开头"
        Accessible.name: "停止"
        onClicked: root.audioPlayer.stop()
    }

    StatusBadge {
        visible: !root.narrowMode
        theme: root.theme
        typography: root.typography
        label: root.audioPlayer
            ? root.stateLabel(root.audioPlayer.playerState)
            : "未加载"
        tone: root.audioPlayer && root.audioPlayer.playerState === "playing"
            ? "success"
            : root.audioPlayer && root.audioPlayer.playerState === "error"
                ? "danger"
                : root.audioPlayer && root.audioPlayer.playerState === "paused"
                    ? "warning"
                    : "muted"
    }
}

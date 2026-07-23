import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

RowLayout {
    id: root
    objectName: "globalPlaybackDeviceControl"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false
    property bool narrowMode: false

    spacing: root.theme.spacingXs
    implicitHeight: root.compactMode ? 30 : 32

    function outputDeviceIndex() {
        if (!root.audioPlayer)
            return -1
        var devices = root.audioPlayer.outputDevices || []
        for (var index = 0; index < devices.length; index += 1) {
            if (devices[index].id === root.audioPlayer.selectedOutputDeviceId)
                return index
        }
        return -1
    }

    Text {
        visible: !root.narrowMode
        text: "设备"
        color: root.theme.textSecondary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
    }

    ComboBox {
        id: outputDeviceCombo
        objectName: "globalAudioOutputDeviceCombo"
        Layout.preferredWidth: root.narrowMode ? 152 : 220
        Layout.minimumWidth: root.narrowMode ? 128 : 170
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        enabled: root.audioPlayer && root.audioPlayer.backendInitialized
        hoverEnabled: true
        model: root.audioPlayer ? root.audioPlayer.outputDevices : []
        textRole: "name"
        valueRole: "id"
        currentIndex: root.outputDeviceIndex()
        displayText: currentIndex >= 0
            ? currentText
            : root.audioPlayer && root.audioPlayer.outputDeviceName.length > 0
                ? root.audioPlayer.outputDeviceName
                : "选择输出设备"

        onDownChanged: {
            if (down && root.audioPlayer)
                root.audioPlayer.refreshOutputDevices()
        }
        onActivated: function(index) {
            var devices = root.audioPlayer
                ? root.audioPlayer.outputDevices
                : []
            if (root.audioPlayer && index >= 0 && index < devices.length)
                root.audioPlayer.selectOutputDevice(devices[index].id)
        }

        contentItem: Text {
            leftPadding: 8
            rightPadding: outputDeviceCombo.indicator.width + 8
            text: outputDeviceCombo.displayText
            color: outputDeviceCombo.enabled
                ? root.theme.textPrimary
                : root.theme.textDisabled
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeSmall
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        background: Rectangle {
            color: outputDeviceCombo.enabled
                ? root.theme.inputBackground
                : root.theme.disabledBackground
            border.color: outputDeviceCombo.visualFocus
                ? root.theme.focusRing
                : root.theme.borderNormal
            border.width: outputDeviceCombo.visualFocus ? 2 : 1
            radius: root.theme.radiusSmall
        }

        ToolTip.visible: hovered
        ToolTip.text: root.audioPlayer
            ? root.audioPlayer.outputDeviceStatus
            : "播放器未初始化"
    }

    WorkstationButton {
        objectName: "globalPlayerMuteButton"
        Layout.preferredWidth: root.narrowMode ? 48 : 70
        implicitHeight: root.compactMode
            ? root.theme.controlHeightSmall
            : root.theme.controlHeightNormal
        theme: root.theme
        typography: root.typography
        text: root.audioPlayer && root.audioPlayer.muted
            ? (root.narrowMode ? "启声" : "取消静音")
            : "静音"
        enabled: root.audioPlayer && root.audioPlayer.backendInitialized
        disabledReason: "当前运行模式未初始化音频输出"
        toolTipText: root.audioPlayer && root.audioPlayer.muted
            ? "恢复音频输出"
            : "将音频输出静音"
        onClicked: root.audioPlayer.setMuted(!root.audioPlayer.muted)
    }

    Text {
        visible: !root.narrowMode
        text: "音量"
        color: root.theme.textSecondary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
    }

    ThemedSlider {
        objectName: "globalPlayerVolumeSlider"
        theme: root.theme
        Layout.preferredWidth: root.narrowMode ? 82 : 110
        Layout.minimumWidth: 68
        enabled: root.audioPlayer && root.audioPlayer.backendInitialized
        from: 0
        to: 100
        value: root.audioPlayer ? root.audioPlayer.volume : 70
        onMoved: root.audioPlayer.setVolume(value)
        Accessible.name: "播放器音量"
        Accessible.description: Math.round(value) + "%"
    }

    Text {
        visible: !root.narrowMode
        Layout.preferredWidth: 36
        text: root.audioPlayer ? root.audioPlayer.volume + "%" : "70%"
        color: root.theme.textPrimary
        font.family: root.typography.fontFamily
        font.pixelSize: root.typography.sizeSmall
        horizontalAlignment: Text.AlignRight
    }
}

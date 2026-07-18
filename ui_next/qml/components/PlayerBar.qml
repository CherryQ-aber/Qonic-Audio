import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer
    implicitHeight: playerContent.implicitHeight + theme.spacing * 2
    color: theme.panel
    border.color: theme.border
    border.width: 1
    radius: theme.radiusSmall

    function formatTime(milliseconds) { var seconds = Math.max(0, Math.floor(milliseconds / 1000)); return Math.floor(seconds / 60) + ":" + ((seconds % 60) < 10 ? "0" : "") + (seconds % 60) }
    function stateTone(state) { return state === "playing" ? "success" : state === "paused" ? "warning" : "muted" }
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

    ColumnLayout {
        id: playerContent
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: root.theme.spacing
        spacing: 7

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8
            TransportButton { text: "播放"; enabled: root.audioPlayer && root.audioPlayer.canPlay; onClicked: root.audioPlayer.play() }
            TransportButton { text: "暂停"; enabled: root.audioPlayer && root.audioPlayer.playerState === "playing"; onClicked: root.audioPlayer.pause() }
            TransportButton { text: "停止"; enabled: root.audioPlayer && root.audioPlayer.hasCurrentFile && root.audioPlayer.playerState !== "empty"; onClicked: root.audioPlayer.stop() }
            StatusBadge { theme: root.theme; typography: root.typography; label: root.audioPlayer ? (root.audioPlayer.playerState === "playing" ? "播放中" : root.audioPlayer.playerState === "paused" ? "已暂停" : root.audioPlayer.playerState === "ready" ? "已加载" : root.audioPlayer.playerState === "error" ? "错误" : "已停止") : "未加载"; tone: root.audioPlayer ? root.stateTone(root.audioPlayer.playerState) : "muted" }
            Text { text: root.audioPlayer ? root.formatTime(root.audioPlayer.position) + " / " + root.formatTime(root.audioPlayer.duration) : "0:00 / 0:00"; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; Layout.minimumWidth: 0; horizontalAlignment: Text.AlignRight }
        }

        ThemedSlider {
            id: progressSlider
            property bool seekPending: false
            property real pendingPosition: 0
            theme: root.theme
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            enabled: root.audioPlayer && root.audioPlayer.audioPlaybackEnabled && root.audioPlayer.duration > 0
            from: 0
            to: root.audioPlayer ? Math.max(1, root.audioPlayer.duration) : 1
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

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8
            Text {
                text: root.audioPlayer
                    ? "播放源：" + root.audioPlayer.currentPlaybackSourceTypeLabel + " · " + root.audioPlayer.currentPlaybackSourceLabel
                    : "播放源：未加载"
                color: root.theme.textSecondary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideMiddle
                maximumLineCount: 1
            }
            Text { text: "输出设备"; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall }
            ComboBox {
                id: outputDeviceCombo
                objectName: "audioOutputDeviceCombo"
                Layout.preferredWidth: 220
                Layout.minimumWidth: 150
                enabled: root.audioPlayer && root.audioPlayer.backendInitialized
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
                    var devices = root.audioPlayer ? root.audioPlayer.outputDevices : []
                    if (root.audioPlayer && index >= 0 && index < devices.length)
                        root.audioPlayer.selectOutputDevice(devices[index].id)
                }
                contentItem: Text {
                    leftPadding: 8
                    rightPadding: outputDeviceCombo.indicator.width + 8
                    text: outputDeviceCombo.displayText
                    color: outputDeviceCombo.enabled ? root.theme.textPrimary : root.theme.muted
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeSmall
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }
                background: Rectangle {
                    color: outputDeviceCombo.enabled ? root.theme.inputBackground : root.theme.disabledBackground
                    border.color: outputDeviceCombo.visualFocus ? root.theme.focusRing : root.theme.borderNormal
                    border.width: outputDeviceCombo.visualFocus ? 2 : 1
                    radius: root.theme.radiusSmall
                }
            }
            Text { text: "音量"; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall }
            ThemedSlider { theme: root.theme; Layout.preferredWidth: 120; Layout.minimumWidth: 72; enabled: root.audioPlayer && root.audioPlayer.audioPlaybackEnabled; from: 0; to: 100; value: root.audioPlayer ? root.audioPlayer.volume : 70; onMoved: root.audioPlayer.setVolume(value) }
            Text { text: root.audioPlayer ? root.audioPlayer.volume + "%" : "70%"; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.preferredWidth: 36; horizontalAlignment: Text.AlignRight }
        }

        Text {
            visible: root.audioPlayer
            text: root.audioPlayer ? root.audioPlayer.outputDeviceStatus : ""
            color: root.theme.textSecondary
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeTiny
            Layout.fillWidth: true
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text { visible: root.audioPlayer && root.audioPlayer.error !== ""; text: root.audioPlayer ? root.audioPlayer.error : ""; color: root.theme.error; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }

    component TransportButton: Button {
        implicitWidth: 60; implicitHeight: 32
        font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall
        contentItem: Text { text: parent.text; color: parent.enabled ? root.theme.textPrimary : root.theme.muted; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font: parent.font }
        background: Rectangle { color: !parent.enabled ? root.theme.disabledBackground : parent.hovered ? root.theme.hoverBackground : root.theme.inputBackground; border.color: parent.visualFocus ? root.theme.focusRing : parent.enabled ? root.theme.selectedIndicator : root.theme.borderSubtle; border.width: parent.visualFocus ? 2 : 1; radius: root.theme.radiusSmall }
    }
}

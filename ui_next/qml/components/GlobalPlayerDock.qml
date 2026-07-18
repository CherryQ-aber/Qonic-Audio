import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root
    objectName: "globalPlayerDock"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var audioPlayer: null
    property bool compactMode: false
    property bool narrowMode: false

    readonly property int requestedHeight: compactMode ? 82 : 96

    implicitHeight: requestedHeight
    color: theme.panel
    border.color: theme.border
    border.width: 1

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: root.theme.spacingSm
        anchors.rightMargin: root.theme.spacingSm
        anchors.topMargin: root.compactMode
            ? root.theme.spacingXs
            : root.theme.spacingSm
        anchors.bottomMargin: root.compactMode
            ? root.theme.spacingXs
            : root.theme.spacingSm
        spacing: root.theme.spacingXs

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            Layout.preferredHeight: root.compactMode ? 30 : 34
            spacing: root.theme.spacingSm

            PlayerMediaInfo {
                Layout.fillWidth: true
                Layout.minimumWidth: root.narrowMode ? 150 : 220
                Layout.preferredWidth: root.narrowMode ? 220 : 340
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
                compactMode: root.compactMode
                narrowMode: root.narrowMode
            }

            PlayerControls {
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
                compactMode: root.compactMode
                narrowMode: root.narrowMode
            }

            SeekStepControls {
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
                compactMode: root.compactMode
                narrowMode: root.narrowMode
            }

            PlaybackDeviceControl {
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
                compactMode: root.compactMode
                narrowMode: root.narrowMode
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            Layout.preferredHeight: root.compactMode ? 28 : 32
            spacing: root.theme.spacingSm

            PlayerTimeline {
                Layout.fillWidth: true
                Layout.minimumWidth: 180
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
                compactMode: root.compactMode
            }

            TimestampTools {
                theme: root.theme
                typography: root.typography
                audioPlayer: root.audioPlayer
                compactMode: root.compactMode
                narrowMode: root.narrowMode
            }
        }
    }
}

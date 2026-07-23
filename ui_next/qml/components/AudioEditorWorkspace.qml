import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../pages"
import "../theme"

Item {
    id: root
    objectName: "audioEditorWorkspace"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string currentEditorPageKey: "fileInfo"
    property bool pageActive: true
    property var fileSession: null
    property var audioPlayer: null
    property var editSession: null
    property var lyricsSync: null
    property var processingSession: null
    property var settings: null
    property bool floatingFileBarExpanded: false
    readonly property string currentFileBarMode: root.settings
        ? root.settings.editorFileBarMode : "fixed"
    readonly property bool floatingFileBar: currentFileBarMode === "floating"

    signal floatingFileBarCollapseRequested()

    enabled: pageActive
    clip: true

    function editorPageIndex(pageKey) {
        if (pageKey === "lyrics")
            return 1
        if (pageKey === "audioProcessing")
            return 2
        return 0
    }

    StackLayout {
        id: editorPageStack
        objectName: "editorPageStack"
        anchors.fill: parent
        anchors.topMargin: root.floatingFileBar
            ? 0 : currentFileBar.height + root.theme.spacing
        currentIndex: root.editorPageIndex(root.currentEditorPageKey)

        MetadataPage {
            objectName: "fileInfoPage"
            Layout.fillWidth: true
            Layout.fillHeight: true
            enabled: root.pageActive && editorPageStack.currentIndex === 0
            theme: root.theme
            typography: root.typography
            audioPlayer: root.audioPlayer
            editSession: root.editSession
        }

        LyricsCoverPage {
            objectName: "lyricsPage"
            Layout.fillWidth: true
            Layout.fillHeight: true
            enabled: root.pageActive && editorPageStack.currentIndex === 1
            pageActive: enabled
            theme: root.theme
            typography: root.typography
            audioPlayer: root.audioPlayer
            editSession: root.editSession
            lyricsSync: root.lyricsSync
        }

        AudioProcessingPage {
            objectName: "audioProcessingPage"
            Layout.fillWidth: true
            Layout.fillHeight: true
            enabled: root.pageActive && editorPageStack.currentIndex === 2
            theme: root.theme
            typography: root.typography
            processingSession: root.processingSession
        }
    }

    CurrentFileBar {
        id: currentFileBar
        objectName: "audioEditorCurrentFileCard"
        x: root.floatingFileBar ? root.theme.spacing : 0
        y: root.floatingFileBar
            ? (root.floatingFileBarExpanded
                ? 0
                : -height - root.theme.spacing)
            : 0
        width: root.width - (root.floatingFileBar ? root.theme.spacing * 2 : 0)
        z: root.floatingFileBar ? 10 : 0
        floatingMode: root.floatingFileBar
        expanded: root.floatingFileBarExpanded
        enabled: !root.floatingFileBar || root.floatingFileBarExpanded
        opacity: !root.floatingFileBar || root.floatingFileBarExpanded ? 1 : 0
        theme: root.theme
        typography: root.typography
        fileSession: root.fileSession
        editSession: root.editSession
        audioPlayer: root.audioPlayer
        processingSession: root.processingSession
        onCollapseRequested: root.floatingFileBarCollapseRequested()

        Behavior on y {
            enabled: root.floatingFileBar
            NumberAnimation {
                duration: root.theme.durationNormal
                easing.type: Easing.OutCubic
            }
        }

        Behavior on opacity {
            NumberAnimation { duration: root.theme.durationFast }
        }
    }

    DropArea {
        id: workspaceDropArea
        objectName: "audioEditorDropArea"
        anchors.fill: parent
        z: 20
        enabled: root.pageActive

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
        color: Qt.rgba(
            root.theme.accent.r,
            root.theme.accent.g,
            root.theme.accent.b,
            0.12
        )
        border.color: root.theme.accent
        border.width: 1
        radius: root.theme.radiusSmall

        Text {
            anchors.centerIn: parent
            width: Math.min(parent.width - root.theme.spacing * 4, 520)
            text: "拖入一个音频文件，或拖入音频与同名 .lrc\n载入编辑会话和播放器，但不会自动播放。"
            color: root.theme.textPrimary
            font.family: root.typography.fontFamily
            font.pixelSize: root.typography.sizeMedium
            font.weight: root.typography.weightBold
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
    }
}

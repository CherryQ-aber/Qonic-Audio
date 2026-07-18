import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../pages"
import "../theme"

Item {
    id: root
    objectName: "workspaceStack"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string currentWorkspaceKey: "autoConvert"
    property string currentEditorPageKey: "fileInfo"
    property bool legacyAnalysisOpen: false
    property var fileSession: null
    property var fileBrowser: null
    property var audioPlayer: null
    property var editSession: null
    property var processingSession: null

    signal closeLegacyAnalysisRequested()

    function editorPageIndex(pageKey) {
        if (pageKey === "lyrics")
            return 1
        if (pageKey === "audioProcessing")
            return 2
        return 0
    }

    StackLayout {
        id: primaryWorkspaceStack
        objectName: "primaryWorkspaceStack"
        anchors.fill: parent
        currentIndex: root.currentWorkspaceKey === "audioEditor" ? 1 : 0
        enabled: !root.legacyAnalysisOpen

        Item {
            id: autoConvertWorkspace
            objectName: "autoConvertWorkspace"
            enabled: primaryWorkspaceStack.currentIndex === 0

            AutoConvertPage {
                anchors.fill: parent
                theme: root.theme
                typography: root.typography
                pageActive: autoConvertWorkspace.enabled
            }
        }

        Item {
            id: audioEditorWorkspace
            objectName: "audioEditorWorkspace"
            enabled: primaryWorkspaceStack.currentIndex === 1

            StackLayout {
                id: editorPageStack
                objectName: "editorPageStack"
                anchors.fill: parent
                currentIndex: root.editorPageIndex(root.currentEditorPageKey)

                MetadataPage {
                    objectName: "fileInfoPage"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    enabled: audioEditorWorkspace.enabled
                        && editorPageStack.currentIndex === 0
                    theme: root.theme
                    typography: root.typography
                    audioPlayer: root.audioPlayer
                    editSession: root.editSession
                }

                LyricsCoverPage {
                    objectName: "lyricsPage"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    enabled: audioEditorWorkspace.enabled
                        && editorPageStack.currentIndex === 1
                    pageActive: enabled
                    theme: root.theme
                    typography: root.typography
                    audioPlayer: root.audioPlayer
                    editSession: root.editSession
                }

                AudioEditorPage {
                    objectName: "audioProcessingPage"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    enabled: audioEditorWorkspace.enabled
                        && editorPageStack.currentIndex === 2
                    pageActive: enabled
                    theme: root.theme
                    typography: root.typography
                    fileSession: root.fileSession
                    fileBrowser: root.fileBrowser
                    audioPlayer: root.audioPlayer
                    editSession: root.editSession
                    processingSession: root.processingSession
                }
            }
        }
    }

    Rectangle {
        id: legacyAnalysisLayer
        anchors.fill: parent
        z: 10
        visible: root.legacyAnalysisOpen
        enabled: visible
        color: root.theme.surface
        border.color: root.theme.border
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.theme.spacing
            spacing: root.theme.spacing

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: "Legacy 兼容入口"
                    color: root.theme.textSecondary
                    font.family: root.typography.fontFamily
                    font.pixelSize: root.typography.sizeSmall
                    Layout.fillWidth: true
                }

                WorkstationButton {
                    id: closeLegacyAnalysisButton
                    objectName: "closeLegacyAnalysisButton"
                    Layout.preferredWidth: 112
                    theme: root.theme
                    typography: root.typography
                    text: "返回工作区"
                    tone: "ghost"
                    onClicked: root.closeLegacyAnalysisRequested()
                }
            }

            AnalysisPage {
                objectName: "legacyAnalysisPage"
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: root.theme
                typography: root.typography
            }
        }
    }

    onLegacyAnalysisOpenChanged: {
        if (legacyAnalysisOpen)
            Qt.callLater(closeLegacyAnalysisButton.forceActiveFocus)
    }
}

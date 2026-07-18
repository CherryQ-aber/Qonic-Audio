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
    property var settings: null
    property bool editorFileBarExpanded: false
    property real applicationWidth: width
    property real applicationHeight: height

    signal closeLegacyAnalysisRequested()
    signal editorFileBarCollapseRequested()

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
                applicationWidth: root.applicationWidth
                applicationHeight: root.applicationHeight
            }
        }

        AudioEditorWorkspace {
            id: audioEditorWorkspace
            objectName: "audioEditorWorkspace"
            enabled: primaryWorkspaceStack.currentIndex === 1
            pageActive: enabled
            currentEditorPageKey: root.currentEditorPageKey
            theme: root.theme
            typography: root.typography
            fileSession: root.fileSession
            audioPlayer: root.audioPlayer
            editSession: root.editSession
            processingSession: root.processingSession
            settings: root.settings
            floatingFileBarExpanded: root.editorFileBarExpanded
            onFloatingFileBarCollapseRequested:
                root.editorFileBarCollapseRequested()
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

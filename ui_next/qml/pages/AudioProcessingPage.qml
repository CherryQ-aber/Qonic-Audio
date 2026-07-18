import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var processingSession

    Flickable {
        id: pageScroll
        objectName: "audioProcessingPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: processingContent.implicitHeight + root.theme.spacing * 2
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ThemeScrollBar {
            theme: root.theme
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: processingContent
            objectName: "audioProcessingPageContent"
            width: pageScroll.width
            Layout.minimumWidth: 0
            spacing: root.theme.spacing

            PitchShiftCard {
                objectName: "audioEditorPitchCard"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                theme: root.theme
                typography: root.typography
                processingSession: root.processingSession
            }

            Item {
                Layout.minimumHeight: root.theme.spacing
            }
        }
    }
}

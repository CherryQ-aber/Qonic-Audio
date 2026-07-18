import QtQuick
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var processingSession

    // Anchored children do not contribute to an Item's implicit size.  The
    // outer editor Flickable therefore needs the processing stack explicitly.
    implicitHeight: processingContent.implicitHeight

    ColumnLayout {
        id: processingContent
        anchors.fill: parent
        spacing: theme.spacing

        // The outer editor Flickable owns page scrolling.  Pitch keeps its
        // safety note, parameters, preview and export in one responsive card.
        PitchShiftCard {
            objectName: "audioEditorPitchCard"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            theme: root.theme
            typography: root.typography
            processingSession: root.processingSession
        }
    }
}

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

    function resetPageScrollIfContentFits() {
        if (pageScroll.contentHeight <= pageScroll.height + 0.5
                && pageScroll.contentY !== 0) {
            pageScroll.contentY = 0
        }
    }

    Flickable {
        id: pageScroll
        objectName: "audioProcessingPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: Math.max(height, processingContent.implicitHeight)
        boundsBehavior: Flickable.StopAtBounds
        onHeightChanged: root.resetPageScrollIfContentFits()
        onContentHeightChanged: root.resetPageScrollIfContentFits()

        ScrollBar.vertical: ThemeScrollBar {
            theme: root.theme
            policy: ScrollBar.AsNeeded
            visible: size < 0.999
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
        }
    }
}

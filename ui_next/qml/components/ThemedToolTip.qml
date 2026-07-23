import QtQuick
import QtQuick.Controls

import "../theme"

ToolTip {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}

    delay: 450
    timeout: 5000
    padding: theme.spacingSm

    contentItem: Text {
        text: root.text
        color: theme.textPrimary
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall
        wrapMode: Text.WordWrap
    }

    background: Rectangle {
        color: theme.drawerBackground
        border.color: theme.borderStrong
        border.width: 1
        radius: theme.radiusSmall
    }
}

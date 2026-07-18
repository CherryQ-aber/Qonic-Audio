import QtQuick
import QtQuick.Controls

import "../theme"

ScrollBar {
    id: root

    property QtObject theme: Theme {}

    implicitWidth: 10
    implicitHeight: 10
    padding: 2

    contentItem: Rectangle {
        implicitWidth: 6
        implicitHeight: 6
        radius: 3
        color: root.pressed ? theme.selectedIndicator
            : root.hovered ? theme.borderStrong
            : theme.borderNormal
        opacity: root.active || root.policy === ScrollBar.AlwaysOn ? 1.0 : 0.72
    }

    background: Rectangle {
        color: "transparent"
    }
}

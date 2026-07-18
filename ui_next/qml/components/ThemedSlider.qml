import QtQuick
import QtQuick.Controls

import "../theme"

Slider {
    id: root

    property QtObject theme: Theme {}

    implicitHeight: theme.controlHeightNormal

    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: 4
        radius: 2
        color: root.enabled ? theme.borderSubtle : theme.disabledBackground

        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: root.enabled ? theme.selectedIndicator : theme.textDisabled
        }
    }

    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: 14
        height: 14
        radius: 7
        color: root.enabled ? theme.panelBackgroundRaised : theme.disabledBackground
        border.color: root.visualFocus ? theme.focusRing : root.enabled ? theme.selectedIndicator : theme.borderNormal
        border.width: root.visualFocus ? 2 : 1
    }
}

import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string label: ""
    property string tone: "muted"

    implicitWidth: labelText.implicitWidth + 18
    implicitHeight: 24
    radius: theme.radiusSmall
    color: badgeColor(tone)
    border.color: theme.badgeBorder
    border.width: 1

    Behavior on color { ColorAnimation { duration: theme.durationFast } }
    Behavior on border.color { ColorAnimation { duration: theme.durationFast } }

    function badgeColor(value) {
        if (value === "accent") {
            return Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.18)
        }
        if (value === "success") {
            return Qt.rgba(theme.success.r, theme.success.g, theme.success.b, 0.18)
        }
        if (value === "warning") {
            return Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.18)
        }
        if (value === "danger") {
            return Qt.rgba(theme.danger.r, theme.danger.g, theme.danger.b, 0.18)
        }
        return Qt.rgba(theme.muted.r, theme.muted.g, theme.muted.b, 0.16)
    }

    Text {
        id: labelText
        anchors.centerIn: parent
        text: root.label
        color: theme.textPrimary
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall
        font.weight: typography.weightMedium
        elide: Text.ElideRight
        maximumLineCount: 1
    }
}

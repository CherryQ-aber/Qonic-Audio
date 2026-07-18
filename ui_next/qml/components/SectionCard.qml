import QtQuick

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property string tone: "normal" // normal, warning, error, success
    property bool raised: false

    color: raised ? theme.panelBackgroundRaised : theme.panelBackground
    border.color: tone === "warning" ? theme.warning
        : tone === "error" ? theme.error
        : tone === "success" ? theme.success : theme.borderNormal
    border.width: 1
    radius: theme.radiusSmall

    Behavior on color { ColorAnimation { duration: theme.durationNormal } }
    Behavior on border.color { ColorAnimation { duration: theme.durationFast } }
}

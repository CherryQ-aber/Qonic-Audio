import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Button {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string tone: "secondary" // primary, secondary, ghost, warning, error
    property string iconName: ""
    property bool loading: false
    property string disabledReason: ""
    property string toolTipText: ""

    implicitHeight: theme.controlHeightNormal
    hoverEnabled: true
    activeFocusOnTab: enabled
    focusPolicy: enabled ? Qt.TabFocus : Qt.NoFocus
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.description: disabledReason || toolTipText || text

    readonly property bool semanticTone: tone === "warning" || tone === "error"
    readonly property color toneColor: tone === "warning" ? theme.warning
        : tone === "error" ? theme.error : theme.selectedIndicator

    contentItem: RowLayout {
        spacing: root.iconName === "" ? 0 : theme.spacingXs

        ActionIcon {
            theme: root.theme
            typography: root.typography
            name: root.loading ? "" : root.iconName
            enabledState: root.enabled
            tone: root.tone === "error" ? "error" : root.tone === "warning" ? "warning" : "normal"
            Layout.alignment: Qt.AlignVCenter
        }

        Text {
            Layout.fillWidth: true
            text: root.loading ? "处理中…" : root.text
            color: !root.enabled ? theme.textDisabled
                : root.semanticTone ? root.toneColor
                : root.tone === "primary" ? theme.textPrimary : theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: root.tone === "primary" ? typography.weightBold : typography.weightMedium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    background: Rectangle {
        color: !root.enabled ? theme.disabledBackground
            : root.pressed ? theme.pressedBackground
            : root.hovered ? theme.hoverBackground
            : root.tone === "primary" ? theme.selectedBackground
            : root.tone === "ghost" ? "transparent" : theme.inputBackground
        border.color: root.visualFocus ? theme.focusRing
            : root.semanticTone ? root.toneColor
            : root.tone === "primary" ? theme.selectedIndicator : theme.borderNormal
        border.width: root.visualFocus ? 2 : 1
        radius: theme.radiusSmall

        Behavior on color { ColorAnimation { duration: theme.durationFast } }
        Behavior on border.color { ColorAnimation { duration: theme.durationFast } }
    }

    ThemedToolTip {
        theme: root.theme
        typography: root.typography
        visible: root.hovered && ((!root.enabled && root.disabledReason !== "") || root.toolTipText !== "")
        text: !root.enabled && root.disabledReason !== "" ? root.disabledReason : root.toolTipText
    }
}

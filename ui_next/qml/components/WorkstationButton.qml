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
    property bool selectedState: false
    property bool borderless: false
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
    readonly property color selectedBackgroundColor: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.10 : 0.14
    )
    readonly property color selectedHoverBackgroundColor: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.16 : 0.20
    )
    readonly property color selectedPressedBackgroundColor: Qt.rgba(
        theme.selectedIndicator.r,
        theme.selectedIndicator.g,
        theme.selectedIndicator.b,
        theme.isLight ? 0.22 : 0.26
    )

    contentItem: RowLayout {
        spacing: root.iconName === "" ? 0 : theme.spacingXs

        ActionIcon {
            theme: root.theme
            typography: root.typography
            name: root.loading ? "" : root.iconName
            enabledState: root.enabled
            tone: root.tone === "error" ? "error"
                : root.tone === "warning" ? "warning"
                : root.selectedState ? "accent" : "normal"
            Layout.alignment: Qt.AlignVCenter
        }

        Text {
            Layout.fillWidth: true
            text: root.loading ? "处理中…" : root.text
            color: !root.enabled ? theme.textDisabled
                : root.semanticTone ? root.toneColor
                : theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: root.tone === "primary" || root.selectedState
                ? typography.weightBold : typography.weightMedium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    background: Rectangle {
        color: !root.enabled ? theme.disabledBackground
            : root.selectedState && root.pressed
                ? root.selectedPressedBackgroundColor
            : root.selectedState && root.hovered
                ? root.selectedHoverBackgroundColor
            : root.pressed ? theme.pressedBackground
            : root.hovered ? theme.hoverBackground
            : root.selectedState ? root.selectedBackgroundColor
            : root.tone === "primary" ? theme.selectedBackground
            : root.tone === "ghost" ? "transparent" : theme.inputBackground
        border.color: root.visualFocus ? theme.focusRing
            : root.semanticTone ? root.toneColor
            : root.selectedState || root.tone === "primary"
                ? theme.selectedIndicator
            : root.borderless && root.tone === "ghost"
                ? "transparent" : theme.borderNormal
        border.width: root.visualFocus ? 2
            : root.selectedState ? 1
            : root.borderless && root.tone === "ghost" ? 0 : 1
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

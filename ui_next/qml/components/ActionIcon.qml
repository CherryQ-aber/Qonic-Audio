import QtQuick

import "../theme"

// Deliberately small, monochrome action glyph set. These are not emoji and
// remain supplemental to visible text (or Accessible.name on icon-only use).
Text {
    id: root

    property QtObject theme: Theme {}
    property string name: ""
    property bool enabledState: true
    property string tone: "normal"

    readonly property var glyphs: ({
        "refresh": "↻",
        "open": "↗",
        "close": "×",
        "clear": "×",
        "expand": "⌄",
        "collapse": "⌃",
        "log": "≡",
        "details": "›"
    })

    text: glyphs[name] || ""
    visible: text !== ""
    color: !enabledState ? theme.textDisabled
        : tone === "warning" ? theme.warning
        : tone === "error" ? theme.error : theme.textSecondary
    font.family: typography.fontFamily
    font.pixelSize: theme.iconSizeNormal
    font.weight: Font.DemiBold
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter

    property QtObject typography: Typography {}
}

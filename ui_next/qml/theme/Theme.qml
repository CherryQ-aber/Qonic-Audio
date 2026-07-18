import QtQuick

// Session-only visual tokens. Theme selection lives in this QML object and is
// deliberately not connected to SettingsViewModel or config.json.
QtObject {
    id: root

    property string requestedMode: "dark"
    readonly property string mode: requestedMode === "light" ? "light" : "dark"
    readonly property bool isLight: mode === "light"

    function setMode(nextMode) {
        requestedMode = nextMode === "light" ? "light" : "dark"
    }

    // Background hierarchy
    readonly property color windowBackground: isLight ? "#eef1ef" : "#141615"
    readonly property color workspaceBackground: isLight ? "#f5f6f4" : "#1d201f"
    readonly property color panelBackground: isLight ? "#ffffff" : "#242827"
    readonly property color panelBackgroundRaised: isLight ? "#fafbf9" : "#2b302f"
    readonly property color inputBackground: isLight ? "#ffffff" : "#1a1d1c"
    readonly property color overlayBackground: isLight ? "#26302c33" : "#00000052"
    readonly property color drawerBackground: isLight ? "#fbfcfa" : "#262b29"

    // Text
    readonly property color textPrimary: isLight ? "#1d2723" : "#eee9df"
    readonly property color textSecondary: isLight ? "#52605a" : "#aeb6b1"
    readonly property color textMuted: isLight ? "#718078" : "#737b78"
    readonly property color textDisabled: isLight ? "#98a29d" : "#6b7470"
    readonly property color textInverse: isLight ? "#ffffff" : "#171a18"
    readonly property color linkText: isLight ? "#1e756a" : "#79c8b8"

    // Borders and focus
    readonly property color borderSubtle: isLight ? "#dce2de" : "#303533"
    readonly property color borderNormal: isLight ? "#c6cfca" : "#3b403f"
    readonly property color borderStrong: isLight ? "#8c9a92" : "#68716d"
    readonly property color divider: isLight ? "#d6ddd8" : "#353b38"
    readonly property color focusRing: isLight ? "#17786b" : "#60b7a7"

    // Interaction
    readonly property color hoverBackground: isLight ? "#dcece733" : "#60b7a718"
    readonly property color pressedBackground: isLight ? "#c3ddd633" : "#60b7a72e"
    readonly property color selectedBackground: isLight ? "#b8ddd433" : "#60b7a729"
    readonly property color selectedIndicator: isLight ? "#1e8a7a" : "#60b7a7"
    readonly property color disabledBackground: isLight ? "#e8ece9" : "#2a2e2c"

    // Semantic states. Backgrounds are deliberately soft; labels remain legible.
    readonly property color info: isLight ? "#2c6e9b" : "#68a9cf"
    readonly property color infoBackground: isLight ? "#dcecf7" : "#234052"
    readonly property color success: isLight ? "#2c7a4b" : "#68a874"
    readonly property color successBackground: isLight ? "#dcefe1" : "#23412c"
    readonly property color warning: isLight ? "#956719" : "#c49a52"
    readonly property color warningBackground: isLight ? "#f6ead2" : "#4a3b21"
    readonly property color error: isLight ? "#ad453d" : "#cf6d63"
    readonly property color errorBackground: isLight ? "#f7dfdd" : "#4b2928"

    // Dimensions
    readonly property int spacingXs: 4
    readonly property int spacingSm: 8
    readonly property int spacingMd: 12
    readonly property int spacingLg: 16
    readonly property int spacingXl: 24
    readonly property int radiusSmall: 3
    readonly property int radiusMedium: 6
    readonly property int radiusLarge: 8
    readonly property int controlHeightSmall: 28
    readonly property int controlHeightNormal: 32
    readonly property int controlHeightLarge: 36
    readonly property int sidebarWidth: 218
    readonly property int inspectorMinimumWidth: 272
    readonly property int inspectorWidth: 292
    readonly property int inspectorMaximumWidth: 340

    // Font scale tokens. Typography.qml remains the shared font-family/weight source.
    readonly property int fontCaption: 11
    readonly property int fontBody: 13
    readonly property int fontBodyStrong: 13
    readonly property int fontSubtitle: 15
    readonly property int fontTitle: 20
    readonly property int fontPageTitle: 24

    // Icon scale: monochrome glyphs only, always paired with text or accessible naming.
    readonly property int iconSizeSmall: 12
    readonly property int iconSizeNormal: 14
    readonly property int iconSizeLarge: 16

    // Motion
    readonly property int durationFast: 100
    readonly property int durationNormal: 160
    readonly property int durationSlow: 220

    // Compatibility aliases for the existing component surface.
    readonly property color background: windowBackground
    readonly property color surface: workspaceBackground
    readonly property color panel: panelBackground
    readonly property color border: borderNormal
    readonly property color accent: selectedIndicator
    readonly property color danger: error
    readonly property color muted: textMuted
    readonly property color badgeBorder: isLight ? "#c3ccc7" : "#ffffff14"
    readonly property int spacing: spacingMd
}

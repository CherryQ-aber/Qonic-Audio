import QtQuick

// Central visual tokens. SettingsViewModel owns persistence; this object owns
// only the resolved palette used by the current QML scene.
QtObject {
    id: root

    property string requestedMode: "dark"
    readonly property string mode: ["dark", "light", "black", "purple"].indexOf(requestedMode) >= 0
        ? requestedMode
        : "dark"
    readonly property bool isLight: mode === "light"
    readonly property bool isBlack: mode === "black"
    readonly property bool isPurple: mode === "purple"

    function setMode(nextMode) {
        var normalized = String(nextMode || "dark").toLowerCase()
        requestedMode = ["dark", "light", "black", "purple"].indexOf(normalized) >= 0
            ? normalized
            : "dark"
    }

    function paletteValue(darkValue, lightValue, blackValue, purpleValue) {
        if (isLight)
            return lightValue
        if (isBlack)
            return blackValue
        if (isPurple)
            return purpleValue
        return darkValue
    }

    // Background hierarchy
    readonly property color windowBackground: paletteValue("#141615", "#eef1ef", "#070908", "#15101d")
    readonly property color workspaceBackground: paletteValue("#1d201f", "#f5f6f4", "#0c0f0e", "#1c1627")
    readonly property color panelBackground: paletteValue("#242827", "#ffffff", "#111514", "#251e32")
    readonly property color panelBackgroundRaised: paletteValue("#2b302f", "#fafbf9", "#171b19", "#2e263d")
    readonly property color inputBackground: paletteValue("#1a1d1c", "#ffffff", "#090b0a", "#120f1a")
    readonly property color overlayBackground: paletteValue("#00000052", "#26302c33", "#00000070", "#08050c70")
    readonly property color drawerBackground: paletteValue("#262b29", "#fbfcfa", "#0e1210", "#211a2d")

    // Text
    readonly property color textPrimary: paletteValue("#eee9df", "#1d2723", "#f0f3f1", "#f2ecfa")
    readonly property color textSecondary: paletteValue("#aeb6b1", "#52605a", "#a8b1ad", "#c2b4d2")
    readonly property color textMuted: paletteValue("#737b78", "#718078", "#7a847f", "#9787a8")
    readonly property color textDisabled: paletteValue("#6b7470", "#98a29d", "#545d58", "#6d617a")
    readonly property color textInverse: paletteValue("#171a18", "#ffffff", "#070908", "#17101f")
    readonly property color linkText: paletteValue("#79c8b8", "#1e756a", "#6cc8b5", "#c2a3ff")

    // Borders and focus
    readonly property color borderSubtle: paletteValue("#303533", "#dce2de", "#1c2320", "#342b43")
    readonly property color borderNormal: paletteValue("#3b403f", "#c6cfca", "#2b3430", "#493b5d")
    readonly property color borderStrong: paletteValue("#68716d", "#8c9a92", "#65706b", "#79688f")
    readonly property color divider: paletteValue("#353b38", "#d6ddd8", "#242c28", "#3b304d")
    readonly property color focusRing: paletteValue("#60b7a7", "#17786b", "#57c2ad", "#ae8be8")

    // Interaction
    readonly property color hoverBackground: paletteValue("#60b7a718", "#dcece733", "#57c2ad18", "#ae8be81c")
    readonly property color pressedBackground: paletteValue("#60b7a72e", "#c3ddd633", "#57c2ad2e", "#ae8be836")
    readonly property color selectedBackground: paletteValue("#60b7a729", "#b8ddd433", "#57c2ad29", "#ae8be833")
    readonly property color selectedIndicator: paletteValue("#60b7a7", "#1e8a7a", "#57c2ad", "#ae8be8")
    readonly property color disabledBackground: paletteValue("#2a2e2c", "#e8ece9", "#171b19", "#30283c")

    // Custom window chrome
    readonly property color titleBarInactiveText: paletteValue("#8a928e", "#7a8580", "#7a8580", "#9284a1")
    readonly property color windowControlHover: paletteValue("#ffffff14", "#18251f14", "#ffffff14", "#ffffff16")
    readonly property color windowControlPressed: paletteValue("#ffffff24", "#18251f24", "#ffffff24", "#ffffff29")
    readonly property color windowCloseHover: "#c42b1c"
    readonly property color windowClosePressed: "#9f2218"

    // Semantic states. Backgrounds are deliberately soft; labels remain legible.
    readonly property color info: paletteValue("#68a9cf", "#2c6e9b", "#70b6df", "#91b5e8")
    readonly property color infoBackground: paletteValue("#234052", "#dcecf7", "#162c3a", "#24324f")
    readonly property color success: paletteValue("#68a874", "#2c7a4b", "#70bd7f", "#83bf8f")
    readonly property color successBackground: paletteValue("#23412c", "#dcefe1", "#173420", "#243b2c")
    readonly property color warning: paletteValue("#c49a52", "#956719", "#d4a75c", "#d2a66e")
    readonly property color warningBackground: paletteValue("#4a3b21", "#f6ead2", "#382b16", "#44351f")
    readonly property color error: paletteValue("#cf6d63", "#ad453d", "#df7168", "#e07b8f")
    readonly property color errorBackground: paletteValue("#4b2928", "#f7dfdd", "#3a1d1c", "#4b2736")

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
    readonly property color badgeBorder: paletteValue("#ffffff14", "#c3ccc7", "#ffffff14", "#d9c7f51c")
    readonly property int spacing: spacingMd
}

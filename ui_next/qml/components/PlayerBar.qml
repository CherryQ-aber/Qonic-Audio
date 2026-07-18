import QtQuick

// Compatibility surface retained for older probes and out-of-tree QML users.
// Production pages use the single GlobalPlayerDock instance owned by AppShell.
GlobalPlayerDock {
    id: root
    objectName: "legacyPlayerBar"
    compactMode: false
    narrowMode: width < 1240
}

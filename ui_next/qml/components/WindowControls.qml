import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Item {
    id: root
    objectName: "windowControls"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var windowController: null
    property bool windowActive: true
    property bool windowMaximized: false
    property string nativeHoverControl: windowController
        ? windowController.nativeHoverControl : ""
    property string nativePressedControl: windowController
        ? windowController.nativePressedControl : ""

    signal geometryChanged()

    implicitWidth: 46 * 3
    implicitHeight: 58

    function registerNativeHitRects(targetItem) {
        if (!root.windowController || !targetItem)
            return
        var controls = [
            ["minimize", minimizeButton],
            ["maximize", maximizeButton],
            ["close", closeButton]
        ]
        for (var index = 0; index < controls.length; index += 1) {
            var entry = controls[index]
            var point = entry[1].mapToItem(targetItem, 0, 0)
            root.windowController.setControlRect(
                entry[0],
                point.x,
                point.y,
                entry[1].width,
                entry[1].height
            )
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        WindowControlButton {
            id: minimizeButton
            objectName: "minimizeWindowButton"
            Layout.fillHeight: true
            Layout.preferredWidth: 46
            controlName: "minimize"
            accessibleName: "最小化窗口"
            glyphName: "minimize"
            onClicked: {
                if (root.windowController)
                    root.windowController.minimize()
            }
        }

        WindowControlButton {
            id: maximizeButton
            objectName: "maximizeRestoreWindowButton"
            Layout.fillHeight: true
            Layout.preferredWidth: 46
            controlName: "maximize"
            accessibleName: root.windowMaximized ? "还原窗口" : "最大化窗口"
            glyphName: root.windowMaximized ? "restore" : "maximize"
            onClicked: {
                if (root.windowController)
                    root.windowController.toggleMaximized()
            }
        }

        WindowControlButton {
            id: closeButton
            objectName: "closeWindowButton"
            Layout.fillHeight: true
            Layout.preferredWidth: 46
            controlName: "close"
            accessibleName: root.windowController
                && root.windowController.trayAvailable
                    ? "关闭窗口并保留托盘后台运行"
                    : "关闭窗口"
            glyphName: "close"
            dangerous: true
            onClicked: {
                if (root.windowController)
                    root.windowController.closeWindow()
            }
        }
    }

    onXChanged: geometryChanged()
    onYChanged: geometryChanged()
    onWidthChanged: geometryChanged()
    onHeightChanged: geometryChanged()

    component WindowControlButton: Button {
        id: button

        required property string controlName
        required property string accessibleName
        required property string glyphName
        property bool dangerous: false
        readonly property bool nativeHovered:
            root.nativeHoverControl === controlName
        readonly property bool nativePressed:
            root.nativePressedControl === controlName
        readonly property bool visuallyHovered: hovered || nativeHovered
        readonly property bool visuallyPressed: pressed || nativePressed

        padding: 0
        hoverEnabled: true
        activeFocusOnTab: true
        focusPolicy: Qt.TabFocus
        Accessible.role: Accessible.Button
        Accessible.name: accessibleName

        contentItem: WindowControlGlyph {
            anchors.centerIn: parent
            glyphName: button.glyphName
            iconColor: !button.enabled ? root.theme.textDisabled
                : root.windowActive ? root.theme.textPrimary
                : root.theme.titleBarInactiveText
        }

        background: Rectangle {
            radius: 0
            color: !button.enabled ? "transparent"
                : button.dangerous && button.visuallyPressed
                    ? root.theme.windowClosePressed
                : button.dangerous && button.visuallyHovered
                    ? root.theme.windowCloseHover
                : button.visuallyPressed ? root.theme.windowControlPressed
                : button.visuallyHovered ? root.theme.windowControlHover
                : "transparent"
            border.color: button.visualFocus
                ? root.theme.focusRing : "transparent"
            border.width: button.visualFocus ? 2 : 0

            Behavior on color {
                ColorAnimation { duration: root.theme.durationFast }
            }
        }
    }

    component WindowControlGlyph: Item {
        id: glyph
        required property string glyphName
        required property color iconColor

        implicitWidth: 16
        implicitHeight: 16

        // Button.contentItem stretches to the whole caption button. Keep every
        // glyph inside a fixed centered canvas so normal and maximized states
        // share exactly the same visual center.
        Item {
            objectName: "windowControlGlyphCanvas"
            anchors.centerIn: parent
            width: 16
            height: 16

            Rectangle {
                visible: glyph.glyphName === "minimize"
                anchors.horizontalCenter: parent.horizontalCenter
                y: 10
                width: 10
                height: 1
                color: glyph.iconColor
            }

            Rectangle {
                visible: glyph.glyphName === "maximize"
                anchors.centerIn: parent
                width: 10
                height: 10
                color: "transparent"
                border.color: glyph.iconColor
                border.width: 1
            }

            Item {
                visible: glyph.glyphName === "restore"
                anchors.centerIn: parent
                width: 14
                height: 14

                Rectangle {
                    x: 4
                    y: 2
                    width: 8
                    height: 8
                    color: "transparent"
                    border.color: glyph.iconColor
                    border.width: 1
                }

                Rectangle {
                    x: 2
                    y: 4
                    width: 8
                    height: 8
                    color: "transparent"
                    border.color: glyph.iconColor
                    border.width: 1
                }
            }

            Rectangle {
                visible: glyph.glyphName === "close"
                anchors.centerIn: parent
                width: 12
                height: 1
                rotation: 45
                color: glyph.iconColor
                transformOrigin: Item.Center
            }

            Rectangle {
                visible: glyph.glyphName === "close"
                anchors.centerIn: parent
                width: 12
                height: 1
                rotation: -45
                color: glyph.iconColor
                transformOrigin: Item.Center
            }
        }
    }
}

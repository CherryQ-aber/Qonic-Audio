import QtQuick
import QtQuick.Controls

import "../theme"

ComboBox {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var options: []
    property string value: ""

    signal formatSelected(string value)

    implicitHeight: theme.controlHeightNormal
    model: options
    textRole: "label"
    valueRole: "value"
    font.family: typography.fontFamily
    font.pixelSize: typography.sizeSmall

    function indexForValue(targetValue) {
        for (var index = 0; index < root.options.length; index += 1) {
            if (root.options[index].value === targetValue) {
                return index
            }
        }
        return 0
    }

    function syncIndex() {
        var nextIndex = indexForValue(root.value)
        if (root.currentIndex !== nextIndex) {
            root.currentIndex = nextIndex
        }
    }

    Component.onCompleted: syncIndex()
    onValueChanged: syncIndex()
    onOptionsChanged: syncIndex()
    onActivated: root.formatSelected(root.currentValue)

    background: Rectangle {
        color: !root.enabled ? theme.disabledBackground
            : root.pressed ? theme.pressedBackground
            : root.hovered ? theme.hoverBackground : theme.inputBackground
        border.color: root.activeFocus ? theme.focusRing : theme.borderNormal
        border.width: root.activeFocus ? 2 : 1
        radius: theme.radiusSmall
    }

    contentItem: Text {
        leftPadding: 10
        rightPadding: 24
        text: root.displayText
        color: root.enabled ? theme.textPrimary : theme.textDisabled
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeSmall
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    indicator: ActionIcon {
        theme: root.theme
        typography: root.typography
        x: root.width - width - 8
        y: (root.height - height) / 2
        name: "expand"
        enabledState: root.enabled
        rotation: root.popup.visible ? 180 : 0

        Behavior on rotation { NumberAnimation { duration: theme.durationFast } }
    }

    popup: Popup {
        y: root.height + 2
        width: root.width
        implicitHeight: contentItem.implicitHeight
        padding: 1

        background: Rectangle {
            color: theme.panelBackgroundRaised
            border.color: theme.borderStrong
            radius: theme.radiusSmall
        }

        contentItem: ListView {
            clip: true
            implicitHeight: Math.min(contentHeight, 220)
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex

            ScrollBar.vertical: ThemeScrollBar {
                theme: root.theme
            }
        }
    }

    delegate: ItemDelegate {
        width: root.width
        implicitHeight: 30
        highlighted: root.highlightedIndex === index

        background: Rectangle {
            color: highlighted ? theme.selectedBackground
                : parent.hovered ? theme.hoverBackground : "transparent"
            radius: theme.radiusSmall
        }

        contentItem: Text {
            text: modelData.label
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }
}

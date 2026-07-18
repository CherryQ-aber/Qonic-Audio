import QtQuick
import QtQuick.Layouts

import "../theme"

Rectangle {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string appName: "CherryQ Audio Converter"
    property string moduleName: ""
    property string statusSummary: ""
    property string modeLabel: "预览模式"
    property string capabilityLabel: ""
    property string versionLabel: ""
    property bool inspectorVisible: true
    property bool inspectorCanToggle: true

    signal inspectorToggleRequested()

    implicitHeight: 58
    color: theme.panel
    border.color: theme.border
    border.width: 1

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: theme.spacing + 4
        anchors.rightMargin: theme.spacing + 4
        spacing: theme.spacing

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                text: root.appName
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
            }

            Text {
                text: root.moduleName
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
            }
        }

        StatusBadge {
            objectName: "modeStatusBadge"
            visible: root.modeLabel.length > 0
            theme: root.theme
            typography: root.typography
            label: root.modeLabel
            tone: root.modeLabel === "预览模式" ? "muted" : "accent"
        }

        StatusBadge {
            objectName: "capabilityStatusBadge"
            visible: root.capabilityLabel.length > 0 && root.capabilityLabel !== root.modeLabel
            theme: root.theme
            typography: root.typography
            label: root.capabilityLabel
            tone: root.capabilityLabel === "预览模式" ? "muted" : "accent"
        }

        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: 26
            color: theme.border
        }

        WorkstationButton {
            objectName: "inspectorToggleButton"
            Layout.preferredWidth: root.inspectorVisible ? 110 : 118
            theme: root.theme
            typography: root.typography
            text: root.inspectorVisible ? "隐藏检查器" : "显示检查器"
            iconName: "details"
            tone: "ghost"
            enabled: root.inspectorCanToggle
            disabledReason: root.inspectorCanToggle ? "" : "当前窗口宽度不足；扩大窗口后可重新显示检查器。"
            toolTipText: root.inspectorVisible ? "隐藏右侧检查器" : "显示右侧检查器"
            onClicked: root.inspectorToggleRequested()
        }

        Text {
            text: root.versionLabel
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            horizontalAlignment: Text.AlignRight
        }
    }
}

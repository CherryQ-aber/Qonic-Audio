import QtQuick
import QtQuick.Layouts

import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property string moduleTitle: ""
    property string responsibility: ""
    property var pendingItems: []

    Rectangle {
        anchors.fill: parent
        color: theme.surface

        ColumnLayout {
            anchors.fill: parent
            spacing: theme.spacing

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 112
                color: theme.panel
                border.color: theme.border
                radius: theme.radiusMedium

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.spacing + 4
                    spacing: 8

                    Text {
                        text: root.moduleTitle
                        color: theme.textPrimary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeTitle
                        font.weight: typography.weightBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        text: root.responsibility
                        color: theme.textSecondary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeBody
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                        maximumLineCount: 2
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: theme.spacing

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: theme.panel
                    border.color: theme.border
                    radius: theme.radiusSmall

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: theme.spacing + 4
                        spacing: theme.spacing

                        Text {
                            text: "待迁移内容"
                            color: theme.textPrimary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeMedium
                            font.weight: typography.weightBold
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        Repeater {
                            model: root.pendingItems

                            delegate: Rectangle {
                                required property string modelData

                                Layout.fillWidth: true
                                implicitHeight: 46
                                color: theme.surface
                                border.color: theme.border
                                radius: theme.radiusSmall

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: theme.spacing
                                    anchors.rightMargin: theme.spacing
                                    spacing: 10

                                    Rectangle {
                                        Layout.preferredWidth: 6
                                        Layout.preferredHeight: 6
                                        radius: 3
                                        color: theme.accent
                                    }

                                    Text {
                                        text: modelData
                                        color: theme.textSecondary
                                        font.family: typography.fontFamily
                                        font.pixelSize: typography.sizeBody
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        maximumLineCount: 1
                                    }
                                }
                            }
                        }

                        Item {
                            Layout.fillHeight: true
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 260
                    Layout.fillHeight: true
                    color: theme.panel
                    border.color: theme.border
                    radius: theme.radiusSmall

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: theme.spacing + 4
                        spacing: theme.spacing

                        Text {
                            text: "当前阶段"
                            color: theme.textPrimary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeMedium
                            font.weight: typography.weightBold
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        StatusBadge {
                            theme: root.theme
                            typography: root.typography
                            label: "占位页面"
                            tone: "accent"
                        }

                        Text {
                            text: "本页仅验证 QML 导航、布局、主题与 Python 状态桥接。真实业务逻辑仍保留在旧 Widgets UI。"
                            color: theme.textSecondary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 1
                            color: theme.border
                        }

                        Text {
                            text: "未接入真实文件、队列、播放器、歌词或元数据写回。"
                            color: theme.muted
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Item {
                            Layout.fillHeight: true
                        }
                    }
                }
            }
        }
    }
}

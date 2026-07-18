import QtQuick

Item {
    id: root
    objectName: "folderBrowserPane"

    property var folderBrowserModel: null
    property int defaultPaneWidth: 260
    property int minimumPaneWidth: 220
    property int maximumPaneWidth: 360

    visible: false
    enabled: false
    implicitWidth: visible ? defaultPaneWidth : 0
    implicitHeight: 0
}

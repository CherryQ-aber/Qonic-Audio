import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../theme"

Item {
    id: root
    objectName: "folderBrowserPane"

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var folderBrowserModel: null
    property int defaultPaneWidth: 260
    property int minimumPaneWidth: 220
    property int maximumPaneWidth: 360
    readonly property bool available: folderBrowserModel
        ? Boolean(folderBrowserModel.available)
        : false
    readonly property int itemCount: folderBrowserModel
        ? Number(folderBrowserModel.count)
        : 0
    readonly property bool internalDragActive: folderBrowserModel
        ? Boolean(folderBrowserModel.internalDragActive)
        : false

    signal collapseRequested()
    signal fileDragReleased(
        string fileUrl,
        bool editable,
        bool queueable,
        real paneX,
        real paneY
    )

    implicitWidth: defaultPaneWidth
    implicitHeight: 0

    Rectangle {
        anchors.fill: parent
        color: theme.panelBackground
        border.color: theme.borderNormal
        border.width: 1
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.spacingSm
        spacing: theme.spacingSm

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingXs

            Text {
                Layout.fillWidth: true
                text: "文件浏览"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeMedium
                font.weight: typography.weightBold
                elide: Text.ElideRight
            }

            WorkstationButton {
                objectName: "chooseFolderBrowserRootButton"
                Layout.preferredWidth: 64
                Layout.preferredHeight: theme.controlHeightSmall
                theme: root.theme
                typography: root.typography
                text: "选目录"
                tone: "secondary"
                toolTipText: "显式选择文件浏览根目录；不会扫描入队"
                enabled: root.available
                onClicked: root.folderBrowserModel.chooseRootDirectory()
            }

            WorkstationButton {
                objectName: "collapseFolderBrowserButton"
                Layout.preferredWidth: 44
                Layout.preferredHeight: theme.controlHeightSmall
                theme: root.theme
                typography: root.typography
                text: "收起"
                tone: "ghost"
                toolTipText: "收起全局文件浏览栏"
                onClicked: root.collapseRequested()
            }
        }

        Text {
            objectName: "folderBrowserRootPath"
            Layout.fillWidth: true
            text: root.folderBrowserModel
                ? root.folderBrowserModel.currentRootPath
                : ""
            color: theme.textSecondary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            elide: Text.ElideMiddle
            maximumLineCount: 1
            visible: text.length > 0

            ThemedToolTip {
                theme: root.theme
                typography: root.typography
                visible: rootPathHover.hovered && parent.text.length > 0
                text: parent.text
            }

            HoverHandler {
                id: rootPathHover
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.spacingXs

            ComboBox {
                id: favoriteDirectoriesBox
                objectName: "folderBrowserFavorites"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: theme.controlHeightSmall
                model: root.folderBrowserModel
                    ? root.folderBrowserModel.favoriteDirectories
                    : []
                textRole: "name"
                valueRole: "path"
                displayText: "收藏 " + count
                enabled: root.available && count > 0
                ToolTip.visible: hovered
                ToolTip.text: count > 0
                    ? "切换到收藏目录；右键可清空记录"
                    : "暂无收藏目录"
                onActivated: function(index) {
                    if (root.folderBrowserModel && currentValue)
                        root.folderBrowserModel.openDirectory(String(currentValue))
                }

                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onTapped: folderListsMenu.popup()
                }
            }

            WorkstationButton {
                objectName: "toggleFolderBrowserFavoriteButton"
                Layout.preferredWidth: 34
                Layout.preferredHeight: theme.controlHeightSmall
                theme: root.theme
                typography: root.typography
                text: root.folderBrowserModel
                    && root.folderBrowserModel.currentRootFavorite
                    ? "★"
                    : "☆"
                tone: root.folderBrowserModel
                    && root.folderBrowserModel.currentRootFavorite
                    ? "primary"
                    : "ghost"
                enabled: root.folderBrowserModel
                    && root.folderBrowserModel.hasRoot
                toolTipText: root.folderBrowserModel
                    && root.folderBrowserModel.currentRootFavorite
                    ? "取消收藏当前根目录"
                    : "收藏当前根目录"
                onClicked: root.folderBrowserModel.toggleCurrentRootFavorite()
            }

            ComboBox {
                id: recentDirectoriesBox
                objectName: "folderBrowserRecentDirectories"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                implicitHeight: theme.controlHeightSmall
                model: root.folderBrowserModel
                    ? root.folderBrowserModel.recentDirectories
                    : []
                textRole: "name"
                valueRole: "path"
                displayText: "最近 " + count
                enabled: root.available && count > 0
                ToolTip.visible: hovered
                ToolTip.text: count > 0
                    ? "切换到最近目录；右键可清空记录"
                    : "暂无最近目录"
                onActivated: function(index) {
                    if (root.folderBrowserModel && currentValue)
                        root.folderBrowserModel.openDirectory(String(currentValue))
                }

                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onTapped: folderListsMenu.popup()
                }
            }
        }

        TextField {
            id: searchField
            objectName: "folderBrowserSearchField"
            Layout.fillWidth: true
            implicitHeight: theme.controlHeightNormal
            placeholderText: "筛选音频文件名"
            color: theme.textPrimary
            placeholderTextColor: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            selectByMouse: true
            enabled: root.available
                && root.folderBrowserModel
                && root.folderBrowserModel.hasRoot
            onTextEdited: searchDebounce.restart()

            background: Rectangle {
                color: theme.inputBackground
                border.color: searchField.activeFocus
                    ? theme.focusRing
                    : theme.borderNormal
                border.width: searchField.activeFocus ? 2 : 1
                radius: theme.radiusSmall
            }

            Timer {
                id: searchDebounce
                interval: 180
                repeat: false
                onTriggered: {
                    if (root.folderBrowserModel)
                        root.folderBrowserModel.setSearchText(searchField.text)
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 100

            TreeView {
                id: folderTree
                objectName: "globalFolderTree"
                Accessible.role: Accessible.Tree
                Accessible.name: "全局文件夹树"
                anchors.fill: parent
                clip: true
                // QFileSystemModel populates child rows asynchronously. Keeping
                // pooled delegates here can retain a stale flattened row mapping
                // while a directory is being expanded, which occasionally
                // paints the same children again at the root depth.
                reuseItems: false
                visible: root.folderBrowserModel
                    && root.folderBrowserModel.hasRoot
                model: root.folderBrowserModel
                rootIndex: root.folderBrowserModel
                    ? root.folderBrowserModel.rootModelIndex
                    : undefined
                property int layoutRevision: 0
                columnWidthProvider: function(column) {
                    return Math.max(0, width)
                }
                onRowsChanged: {
                    layoutRevision += 1
                    folderTreeRelayout.restart()
                }

                Timer {
                    id: folderTreeRelayout
                    interval: 0
                    repeat: false
                    onTriggered: folderTree.forceLayout()
                }

                delegate: Rectangle {
                    id: treeDelegate

                    required property var treeView
                    required property bool isTreeNode
                    required property bool expanded
                    required property bool hasChildren
                    required property int depth
                    required property int row
                    required property int column
                    required property bool current
                    required property bool selected
                    required property string filePath
                    required property string fileName
                    required property bool isDirectory
                    required property bool isPlayable
                    required property bool canEnqueue
                    required property bool canEdit
                    required property string fileType
                    required property string pathIdentity
                    required property string fileUrl
                    required property int treeDepth

                    readonly property bool currentSelection:
                        root.folderBrowserModel
                        && root.folderBrowserModel.selectedPathIdentity
                            === treeDelegate.pathIdentity
                    readonly property bool dragEnabled:
                        !treeDelegate.isDirectory
                        && (treeDelegate.isPlayable
                            || treeDelegate.canEdit
                            || treeDelegate.canEnqueue)
                    readonly property bool validTreeDepth:
                        treeDelegate.treeDepth < 0
                        || treeDelegate.depth === treeDelegate.treeDepth

                    implicitWidth: folderTree.width
                    implicitHeight: treeDelegate.validTreeDepth ? 30 : 0
                    visible: treeDelegate.validTreeDepth
                    color: treeDelegate.currentSelection
                        ? Qt.rgba(
                            theme.selectedIndicator.r,
                            theme.selectedIndicator.g,
                            theme.selectedIndicator.b,
                            theme.isLight ? 0.18 : 0.24
                        )
                        : rowMouse.containsMouse
                            ? theme.hoverBackground
                            : "transparent"
                    border.color: treeDelegate.currentSelection
                        ? theme.selectedIndicator
                        : "transparent"
                    border.width: 1
                    radius: theme.radiusSmall
                    activeFocusOnTab: true
                    Accessible.role: treeDelegate.isDirectory
                        ? Accessible.TreeItem
                        : Accessible.ListItem
                    Accessible.name: treeDelegate.fileName
                    Accessible.description: treeDelegate.isDirectory
                        ? "文件夹；按回车展开或折叠"
                        : "音频文件；按回车载入播放器；可拖入当前工作区"
                    Accessible.onPressAction: {
                        if (root.folderBrowserModel) {
                            root.folderBrowserModel.selectPath(
                                treeDelegate.filePath
                            )
                        }
                    }

                    RowLayout {
                        z: 1
                        anchors.fill: parent
                        anchors.leftMargin: 4 + treeDelegate.depth * 14
                        anchors.rightMargin: 4
                        spacing: theme.spacingXs

                        Item {
                            Layout.preferredWidth: 14
                            Layout.fillHeight: true

                            Text {
                                anchors.centerIn: parent
                                text: treeDelegate.isDirectory
                                    ? (treeDelegate.expanded ? "−" : "+")
                                    : "♪"
                                color: treeDelegate.isDirectory
                                    ? theme.textSecondary
                                    : theme.selectedIndicator
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeSmall
                                horizontalAlignment: Text.AlignHCenter
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: treeDelegate.isDirectory
                                    && treeDelegate.hasChildren
                                cursorShape: enabled
                                    ? Qt.PointingHandCursor
                                    : Qt.ArrowCursor
                                onClicked: treeDelegate.treeView.toggleExpanded(
                                    treeDelegate.row
                                )
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: treeDelegate.fileName
                            color: treeDelegate.currentSelection
                                ? theme.selectedIndicator
                                : theme.textPrimary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            font.weight: treeDelegate.currentSelection
                                ? typography.weightMedium
                                : typography.weightRegular
                            elide: Text.ElideRight
                            maximumLineCount: 1
                            verticalAlignment: Text.AlignVCenter
                        }

                        Text {
                            visible: !treeDelegate.isDirectory
                                && folderTree.width >= 300
                            text: treeDelegate.fileType
                            color: theme.textMuted
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                        }
                    }

                    Rectangle {
                        z: 2
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 3
                        color: theme.selectedIndicator
                        visible: treeDelegate.currentSelection
                    }

                    MouseArea {
                        id: rowMouse
                        objectName: "folderTreeRowMouseArea"
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        hoverEnabled: true
                        preventStealing: true
                        cursorShape: Qt.PointingHandCursor
                        drag.target: treeDelegate.dragEnabled
                            ? folderTreeDragProbe
                            : null
                        drag.axis: Drag.XAndYAxis
                        onPositionChanged: {
                            if (!rowMouse.drag.active
                                    || !treeDelegate.dragEnabled
                                    || !root.folderBrowserModel
                                    || root.folderBrowserModel
                                        .internalDragActive) {
                                return
                            }
                            root.folderBrowserModel.beginInternalDrag(
                                treeDelegate.filePath
                            )
                        }
                        onReleased: {
                            if (root.folderBrowserModel
                                    && root.folderBrowserModel
                                        .internalDragActive) {
                                root.folderBrowserModel.finishInternalDrag()
                            }
                            folderTreeDragProbe.x = 0
                            folderTreeDragProbe.y = 0
                        }
                        onCanceled: {
                            if (root.folderBrowserModel
                                    && root.folderBrowserModel
                                        .internalDragActive) {
                                root.folderBrowserModel.cancelInternalDrag()
                            }
                            folderTreeDragProbe.x = 0
                            folderTreeDragProbe.y = 0
                        }
                        onClicked: function(mouse) {
                            if (root.folderBrowserModel)
                                root.folderBrowserModel.selectPath(
                                    treeDelegate.filePath
                                )
                            if (mouse.button === Qt.RightButton) {
                                browserContextMenu.targetPath =
                                    treeDelegate.filePath
                                browserContextMenu.targetDirectory =
                                    treeDelegate.isDirectory
                                browserContextMenu.targetPlayable =
                                    treeDelegate.isPlayable
                                browserContextMenu.targetEditable =
                                    treeDelegate.canEdit
                                browserContextMenu.targetQueueable =
                                    treeDelegate.canEnqueue
                                browserContextMenu.popup()
                            }
                        }
                        onDoubleClicked: function(mouse) {
                            if (mouse.button === Qt.LeftButton
                                    && root.folderBrowserModel
                                    && !treeDelegate.isDirectory
                                    && treeDelegate.isPlayable) {
                                root.folderBrowserModel.requestPlayback(
                                    treeDelegate.filePath
                                )
                            }
                        }
                    }

                    Keys.onReturnPressed: {
                        if (root.folderBrowserModel) {
                            root.folderBrowserModel.selectPath(
                                treeDelegate.filePath
                            )
                            if (treeDelegate.isDirectory) {
                                treeDelegate.treeView.toggleExpanded(
                                    treeDelegate.row
                                )
                            } else if (treeDelegate.isPlayable) {
                                root.folderBrowserModel.requestPlayback(
                                    treeDelegate.filePath
                                )
                            }
                        }
                    }

                    Keys.onMenuPressed: {
                        if (root.folderBrowserModel) {
                            root.folderBrowserModel.selectPath(
                                treeDelegate.filePath
                            )
                            browserContextMenu.targetPath =
                                treeDelegate.filePath
                            browserContextMenu.targetDirectory =
                                treeDelegate.isDirectory
                            browserContextMenu.targetPlayable =
                                treeDelegate.isPlayable
                            browserContextMenu.targetEditable =
                                treeDelegate.canEdit
                            browserContextMenu.targetQueueable =
                                treeDelegate.canEnqueue
                            browserContextMenu.popup()
                        }
                    }

                    ThemedToolTip {
                        theme: root.theme
                        typography: root.typography
                        visible: rowMouse.containsMouse
                        text: treeDelegate.filePath
                    }
                }

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }
            }

            Column {
                anchors.centerIn: parent
                width: Math.max(120, parent.width - theme.spacingLg * 2)
                spacing: theme.spacingSm
                visible: !root.folderBrowserModel
                    || !root.folderBrowserModel.hasRoot

                Text {
                    width: parent.width
                    text: root.available
                        ? "选择一个根目录开始浏览"
                        : "当前运行模式不读取真实目录"
                    color: theme.textSecondary
                    font.family: typography.fontFamily
                    font.pixelSize: typography.sizeSmall
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }

                WorkstationButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 112
                    theme: root.theme
                    typography: root.typography
                    text: "选择目录"
                    tone: "primary"
                    enabled: root.available
                    onClicked: root.folderBrowserModel.chooseRootDirectory()
                }
            }
        }

        Rectangle {
            objectName: "folderBrowserSelectionSummary"
            Layout.fillWidth: true
            Layout.preferredHeight: 66
            color: theme.panelBackgroundRaised
            border.color: theme.borderSubtle
            border.width: 1
            radius: theme.radiusSmall

            RowLayout {
                anchors.fill: parent
                anchors.margins: theme.spacingSm
                spacing: theme.spacingSm

                Rectangle {
                    objectName: "folderBrowserCoverThumbnail"
                    Layout.preferredWidth: 46
                    Layout.preferredHeight: 46
                    color: theme.inputBackground
                    border.color: theme.borderSubtle
                    border.width: 1
                    radius: theme.radiusSmall
                    clip: true

                    Image {
                        id: coverThumbnailImage
                        objectName: "folderBrowserCoverImage"
                        anchors.fill: parent
                        anchors.margins: 2
                        source: root.folderBrowserModel
                            ? root.folderBrowserModel
                                .selectedCoverPreviewUrl
                            : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: false
                        visible: source.toString().length > 0
                    }

                    Text {
                        anchors.centerIn: parent
                        text: root.folderBrowserModel
                            && root.folderBrowserModel.selectedIsDirectory
                            ? "▣"
                            : "♪"
                        color: theme.textMuted
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeMedium
                        visible: !coverThumbnailImage.visible
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 2

                    Text {
                        Layout.fillWidth: true
                        text: root.folderBrowserModel
                            && root.folderBrowserModel.selectedName
                            ? root.folderBrowserModel.selectedName
                            : "未选择项目"
                        color: theme.textPrimary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        font.weight: typography.weightMedium
                        elide: Text.ElideMiddle
                        maximumLineCount: 1
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.folderBrowserModel
                            ? root.folderBrowserModel.selectedSummary
                            : ""
                        color: theme.textSecondary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.folderBrowserModel
                            ? root.folderBrowserModel.selectedCoverStatus
                            : ""
                        color: theme.textMuted
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeTiny
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                }
            }
        }

        Text {
            objectName: "folderBrowserStatus"
            Layout.fillWidth: true
            text: root.folderBrowserModel
                ? root.folderBrowserModel.statusMessage
                : ""
            color: theme.textMuted
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    Item {
        id: folderTreeDragProbe
        width: 1
        height: 1
        visible: false
    }

    Connections {
        target: root.folderBrowserModel
        enabled: root.folderBrowserModel !== null

        function onInternalDragReleased(
            fileUrl,
            editable,
            queueable,
            globalX,
            globalY
        ) {
            var releasePoint = root.mapFromGlobal(globalX, globalY)
            root.fileDragReleased(
                fileUrl,
                editable,
                queueable,
                releasePoint.x,
                releasePoint.y
            )
        }
    }

    Menu {
        id: browserContextMenu
        objectName: "folderBrowserContextMenu"

        property string targetPath: ""
        property bool targetDirectory: false
        property bool targetPlayable: false
        property bool targetEditable: false
        property bool targetQueueable: false

        Action {
            text: "载入播放器"
            enabled: browserContextMenu.targetPlayable
            onTriggered: root.folderBrowserModel.requestPlayback(
                browserContextMenu.targetPath
            )
        }
        Action {
            text: "在音频编辑中打开"
            enabled: browserContextMenu.targetEditable
            onTriggered: root.folderBrowserModel.requestOpenInEditor(
                browserContextMenu.targetPath
            )
        }
        Action {
            text: "加入转码队列"
            enabled: browserContextMenu.targetQueueable
            onTriggered: root.folderBrowserModel.requestAddToQueue(
                browserContextMenu.targetPath
            )
        }
        MenuSeparator {}
        Action {
            text: browserContextMenu.targetDirectory
                ? "打开文件夹"
                : "打开文件位置"
            enabled: browserContextMenu.targetPath.length > 0
            onTriggered: root.folderBrowserModel.openFileLocation(
                browserContextMenu.targetPath
            )
        }
        Action {
            text: "复制文件路径"
            enabled: browserContextMenu.targetPath.length > 0
            onTriggered: root.folderBrowserModel.copyPath(
                browserContextMenu.targetPath
            )
        }
    }

    Menu {
        id: folderListsMenu
        objectName: "folderBrowserListsMenu"

        Action {
            text: "清空收藏目录"
            enabled: root.folderBrowserModel
                && root.folderBrowserModel.favoriteDirectories.length > 0
            onTriggered: root.folderBrowserModel.clearFavoriteDirectories()
        }
        Action {
            text: "清空最近目录"
            enabled: root.folderBrowserModel
                && root.folderBrowserModel.recentDirectories.length > 0
            onTriggered: root.folderBrowserModel.clearRecentDirectories()
        }
    }
}

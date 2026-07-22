import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "components"
import "theme"

ApplicationWindow {
    id: root
    objectName: "appShell"

    // Daily native baseline: 2K display at 125% DPI, windowed rather than maximized.
    width: 1536
    height: 982
    minimumWidth: 1080
    minimumHeight: 680
    visible: true
    color: theme.background
    title: appState.appName + " - " + capabilityGate.userModeLabel

    Theme {
        id: theme
        requestedMode: typeof qmlThemeMode === "string" ? qmlThemeMode : "dark"
    }

    Typography {
        id: typography
    }

    property bool logDrawerOpened: false
    property bool editorFileBarExpanded: false
    property int minimumWorkspaceWidth: 620
    property var folderBrowserBridge:
        typeof folderBrowserModel !== "undefined"
        ? folderBrowserModel
        : null
    property var taskQueueBridge:
        typeof taskQueueModel !== "undefined"
        ? taskQueueModel
        : null
    property var taskQueueFilterBridge:
        typeof taskQueueFilterModel !== "undefined"
        ? taskQueueFilterModel
        : null
    readonly property bool editorFileBarFloating:
        settingsViewModel.editorFileBarMode === "floating"
    readonly property bool folderPaneVisible:
        Boolean(root.folderBrowserBridge
            && root.folderBrowserBridge.available
            && root.folderBrowserBridge.paneVisible)

    function focusCurrentSubNavigation() {
        workspaceSubNavigation.focusCurrentItem()
    }

    function openSettingsOverlay() {
        logDrawerOpened = false
        appState.openSettings()
    }

    function openLogDrawer() {
        if (appState.settingsOverlayOpen)
            appState.closeSettings()
        logDrawerOpened = true
    }

    function closeLogDrawer() {
        logDrawerOpened = false
        Qt.callLater(topStatusBar.focusLogButton)
    }

    function handleFolderFileDragRelease(
        fileUrl,
        editable,
        queueable,
        paneX,
        paneY
    ) {
        var workspacePoint = workspaceSurface.mapFromItem(
            folderBrowserPane,
            paneX,
            paneY
        )
        if (workspacePoint.x < 0
                || workspacePoint.y < 0
                || workspacePoint.x > workspaceSurface.width
                || workspacePoint.y > workspaceSurface.height) {
            return
        }
        if (appState.currentWorkspaceKey === "autoConvert") {
            if (queueable)
                autoConvertViewModel.enqueue_dropped_items([fileUrl])
            return
        }
        if (appState.currentWorkspaceKey === "audioEditor"
                && editable) {
            fileSessionViewModel.handleDroppedUrls([fileUrl])
        }
    }

    onEditorFileBarFloatingChanged: editorFileBarExpanded = false

    ColumnLayout {
        id: shellContent
        anchors.fill: parent
        spacing: 0
        enabled: !root.logDrawerOpened && !appState.settingsOverlayOpen

        TopStatusBar {
            id: topStatusBar
            Layout.fillWidth: true
            theme: theme
            typography: typography
            appName: appState.appName
            moduleName: appState.currentModuleName
            statusSummary: appState.statusSummary
            versionLabel: appState.versionLabel
            workspaces: appState.workspaces
            currentWorkspaceKey: appState.currentWorkspaceKey
            autoConvertActive: autoConvertViewModel.isMonitoring
                || autoConvertViewModel.hasBackgroundTask
            autoConvertStatusText: autoConvertViewModel.hasBackgroundTask
                ? autoConvertViewModel.backgroundTaskLabel
                : autoConvertViewModel.isMonitoring ? "监听中" : ""
            editorHasUnsavedDrafts: editSessionViewModel.hasUnsavedDrafts
            folderBrowserAvailable: Boolean(
                root.folderBrowserBridge
                && root.folderBrowserBridge.available
            )
            folderPaneVisible: root.folderPaneVisible
            onWorkspaceRequested: function(workspaceKey) {
                appState.switchWorkspace(workspaceKey)
            }
            onFolderPaneToggleRequested: {
                if (root.folderBrowserBridge)
                    root.folderBrowserBridge.togglePaneVisible()
            }
            onSettingsRequested: root.openSettingsOverlay()
            onLogRequested: root.openLogDrawer()
        }

        WorkspaceSubNavigation {
            id: workspaceSubNavigation
            Layout.fillWidth: true
            theme: theme
            typography: typography
            currentWorkspaceKey: appState.currentWorkspaceKey
            currentEditorPageKey: appState.currentEditorPageKey
            editorPages: appState.editorPages
            taskQueueModel: root.taskQueueBridge
            taskFilterKey: root.taskQueueFilterBridge
                ? root.taskQueueFilterBridge.filterKey
                : "all"
            editorFileBarFloating: root.editorFileBarFloating
            editorFileBarExpanded: root.editorFileBarExpanded
            onEditorPageRequested: function(pageKey) {
                appState.switchEditorPage(pageKey)
            }
            onTaskFilterRequested: function(filterKey) {
                if (root.taskQueueFilterBridge)
                    root.taskQueueFilterBridge.setFilterKey(filterKey)
            }
            onEditorFileBarToggleRequested:
                root.editorFileBarExpanded = !root.editorFileBarExpanded
        }

        SplitView {
            id: mainArea
            objectName: "mainArea"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            orientation: Qt.Horizontal

            handle: Rectangle {
                implicitWidth: 5
                color: SplitHandle.pressed
                    ? theme.selectedIndicator
                    : SplitHandle.hovered
                        ? theme.borderStrong
                        : theme.borderNormal
            }

            FolderBrowserPane {
                id: folderBrowserPane
                SplitView.minimumWidth: visible ? minimumPaneWidth : 0
                SplitView.preferredWidth: visible
                    ? (root.folderBrowserBridge
                        ? root.folderBrowserBridge.paneWidth
                        : defaultPaneWidth)
                    : 0
                SplitView.maximumWidth: visible ? maximumPaneWidth : 0
                theme: theme
                typography: typography
                folderBrowserModel: root.folderBrowserBridge
                visible: root.folderPaneVisible
                enabled: visible
                onCollapseRequested: {
                    if (root.folderBrowserBridge)
                        root.folderBrowserBridge.setPaneVisible(false)
                }
                onFileDragReleased: function(
                    fileUrl,
                    editable,
                    queueable,
                    paneX,
                    paneY
                ) {
                    root.handleFolderFileDragRelease(
                        fileUrl,
                        editable,
                        queueable,
                        paneX,
                        paneY
                    )
                }
            }

            Rectangle {
                id: workspaceSurface
                objectName: "mainWorkspaceSurface"
                SplitView.minimumWidth: root.minimumWorkspaceWidth
                SplitView.fillWidth: true
                color: theme.surface
                border.color: theme.border
                border.width: 1

                WorkspaceStack {
                    id: workspaceStack
                    anchors.fill: parent
                    anchors.margins: theme.spacing
                    theme: theme
                    typography: typography
                    currentWorkspaceKey: appState.currentWorkspaceKey
                    currentEditorPageKey: appState.currentEditorPageKey
                    legacyAnalysisOpen: appState.legacyAnalysisOpen
                    fileSession: fileSessionViewModel
                    fileBrowser: editorFileBrowserViewModel
                    audioPlayer: audioPlayerViewModel
                    editSession: editSessionViewModel
                    processingSession: processingSessionViewModel
                    settings: settingsViewModel
                    editorFileBarExpanded: root.editorFileBarExpanded
                    applicationWidth: root.width
                    applicationHeight: root.height
                    onEditorFileBarCollapseRequested:
                        root.editorFileBarExpanded = false
                    onCloseLegacyAnalysisRequested: {
                        appState.closeLegacyAnalysis()
                        Qt.callLater(root.focusCurrentSubNavigation)
                    }
                }
            }

            onResizingChanged: {
                if (!resizing
                        && folderBrowserPane.visible
                        && root.folderBrowserBridge) {
                    root.folderBrowserBridge.setPaneWidth(
                        Math.round(folderBrowserPane.width)
                    )
                }
            }
        }

        GlobalPlayerDock {
            id: globalPlayerDock
            Layout.fillWidth: true
            Layout.preferredHeight: requestedHeight
            Layout.minimumHeight: requestedHeight
            Layout.maximumHeight: requestedHeight
            theme: theme
            typography: typography
            audioPlayer: audioPlayerViewModel
            compactMode: root.height < 800
            narrowMode: root.width < 1320
        }
    }

    Rectangle {
        id: folderFileDragIndicator
        objectName: "folderFileDragIndicator"

        readonly property point pointerPosition:
            root.folderBrowserBridge
            ? root.contentItem.mapFromGlobal(
                root.folderBrowserBridge.internalDragGlobalX,
                root.folderBrowserBridge.internalDragGlobalY
            )
            : Qt.point(0, 0)

        z: 1000
        x: Math.max(
            theme.spacingSm,
            Math.min(
                root.width - width - theme.spacingSm,
                pointerPosition.x + 14
            )
        )
        y: Math.max(
            theme.spacingSm,
            Math.min(
                root.height - height - theme.spacingSm,
                pointerPosition.y + 14
            )
        )
        width: Math.min(240, root.width - theme.spacingSm * 2)
        height: 34
        visible: Boolean(
            root.folderBrowserBridge
            && root.folderBrowserBridge.internalDragActive
        )
        color: theme.panelBackgroundRaised
        border.color: theme.selectedIndicator
        border.width: 1
        radius: theme.radiusSmall
        opacity: 0.96

        Text {
            anchors.fill: parent
            anchors.leftMargin: theme.spacingSm
            anchors.rightMargin: theme.spacingSm
            text: "正在拖动 · " + (
                root.folderBrowserBridge
                ? root.folderBrowserBridge.internalDragFileName
                : ""
            )
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightMedium
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideMiddle
            maximumLineCount: 1
        }
    }

    Connections {
        target: appState

        function onCurrentWorkspaceKeyChanged() {
            Qt.callLater(root.focusCurrentSubNavigation)
        }

        function onCurrentEditorPageKeyChanged() {
            Qt.callLater(root.focusCurrentSubNavigation)
        }
    }

    LogDrawer {
        id: logDrawer
        objectName: "logDrawer"
        anchors.fill: parent
        theme: theme
        typography: typography
        logModel: logModel
        globalStatusSummary: appState.statusSummary || "就绪"
        opened: root.logDrawerOpened
        compactLayout: root.width < 1200
        workspaceLeftInset: folderBrowserPane.visible ? folderBrowserPane.width : 0
        workspaceRightInset: 0
        minimumWorkspaceWidth: root.minimumWorkspaceWidth
        onCloseRequested: root.closeLogDrawer()
    }

    SettingsOverlay {
        id: settingsOverlay
        theme: theme
        typography: typography
        openRequested: appState.settingsOverlayOpen
        onCloseRequested: {
            appState.closeSettings()
            Qt.callLater(topStatusBar.focusSettingsButton)
        }
    }

    EditExportDialog {
        id: unifiedEditExportDialog
        theme: theme
        typography: typography
        editSession: editSessionViewModel
    }

    Dialog {
        id: pitchDraftWarningDialog
        modal: true
        visible: processingSessionViewModel.needsDraftConfirmation
        title: "未导出的文件信息草稿"
        standardButtons: Dialog.NoButton
        closePolicy: Popup.NoAutoClose
        anchors.centerIn: parent
        width: Math.min(480, parent.width - theme.spacing * 4)
        contentItem: ColumnLayout {
            spacing: theme.spacing
            Text {
                text: "当前存在未导出的文件信息草稿。本次 Pitch Shift 将基于磁盘上的源文件生成，不会包含这些草稿。"
                color: theme.textPrimary
                font.family: typography.fontFamily
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button {
                    text: "取消"
                    onClicked: processingSessionViewModel.confirmDraftWarning(false)
                }
                Button {
                    text: "继续导出"
                    onClicked: processingSessionViewModel.confirmDraftWarning(true)
                }
            }
        }
    }

    Dialog {
        id: unsavedLyricsDialog
        objectName: "unsavedEditDraftsDialog"
        modal: true
        visible: fileSessionViewModel.hasPendingFileChange
        title: "未导出编辑草稿"
        standardButtons: Dialog.NoButton
        closePolicy: Popup.NoAutoClose
        anchors.centerIn: parent
        width: Math.min(440, parent.width - theme.spacing * 4)

        contentItem: ColumnLayout {
            spacing: theme.spacing
            Text {
                text: fileSessionViewModel.pendingFileName.length > 0
                    ? "当前文件存在未导出的编辑草稿（"
                        + editSessionViewModel.unsavedDraftLabels.join("、")
                        + "）。是否放弃草稿并载入 “"
                        + fileSessionViewModel.pendingFileName + "”？"
                    : "当前文件存在未导出的编辑草稿（"
                        + editSessionViewModel.unsavedDraftLabels.join("、")
                        + "）。是否放弃草稿并清除当前文件？"
                color: theme.textPrimary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeBody
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Text {
                text: "草稿只保存在本次运行内存中；取消会保留当前文件和草稿。"
                color: theme.textSecondary
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeSmall
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button {
                    text: "取消"
                    onClicked: fileSessionViewModel.cancelPendingFileChange()
                }
                Button {
                    text: "放弃草稿并继续"
                    onClicked: fileSessionViewModel.discardPendingFileChange()
                }
            }
        }
    }
}

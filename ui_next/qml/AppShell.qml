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
    property int minimumWorkspaceWidth: 620

    function userFeatureSummary() {
        return capabilityGate.enabledFeatureSummary
    }

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
            modeLabel: capabilityGate.previewMode ? "预览模式" : "正常运行"
            capabilityLabel: capabilityGate.previewMode
                ? ""
                : root.userFeatureSummary()
            versionLabel: appState.versionLabel
            workspaces: appState.workspaces
            currentWorkspaceKey: appState.currentWorkspaceKey
            onWorkspaceRequested: function(workspaceKey) {
                appState.switchWorkspace(workspaceKey)
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
            onEditorPageRequested: function(pageKey) {
                appState.switchEditorPage(pageKey)
            }
        }

        RowLayout {
            id: mainArea
            objectName: "mainArea"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            spacing: 0

            FolderBrowserPane {
                id: folderBrowserPane
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                Layout.preferredWidth: visible ? defaultPaneWidth : 0
                Layout.maximumWidth: visible ? maximumPaneWidth : 0
                visible: false
                enabled: false
            }

            Rectangle {
                id: workspaceSurface
                objectName: "mainWorkspaceSurface"
                Layout.minimumWidth: 0
                Layout.fillWidth: true
                Layout.fillHeight: true
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
                    onCloseLegacyAnalysisRequested: {
                        appState.closeLegacyAnalysis()
                        Qt.callLater(root.focusCurrentSubNavigation)
                    }
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

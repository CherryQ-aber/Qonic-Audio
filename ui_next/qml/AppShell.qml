import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "components"
import "theme"

ApplicationWindow {
    id: root

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

    property var modules: appState.modules
    property var currentModule: moduleByKey(appState.currentModuleKey)
    property string currentPageSource: pageForKey(appState.currentModuleKey)
    property bool logDrawerOpened: false
    property int sidebarWidth: theme.sidebarWidth
    property int inspectorWidth: theme.inspectorWidth
    property int minimumWorkspaceWidth: 620
    // Inspector visibility is session-only. It never writes config.json.
    property bool inspectorUserCollapsed: false
    readonly property int inspectorRequiredWidth: sidebarWidth + inspectorWidth
        + minimumWorkspaceWidth + 2
    readonly property bool inspectorSpaceCollapsed: width < inspectorRequiredWidth
    readonly property bool inspectorDrawerCollapsed: logDrawerOpened
        && width < inspectorRequiredWidth
    readonly property bool inspectorTemporarilyCollapsed: inspectorSpaceCollapsed
        || inspectorDrawerCollapsed
    readonly property bool inspectorPanelVisible: !inspectorUserCollapsed
        && !inspectorTemporarilyCollapsed

    function userFeatureSummary() {
        return capabilityGate.enabledFeatureSummary
    }

    function moduleByKey(moduleKey) {
        for (var index = 0; index < modules.length; index += 1) {
            if (modules[index].key === moduleKey) {
                return modules[index]
            }
        }
        return modules.length > 0 ? modules[0] : {}
    }

    function pageForKey(moduleKey) {
        switch (moduleKey) {
        case "autoConvert":
            return "pages/AutoConvertPage.qml"
        case "audioEditor":
            return "pages/AudioEditorPage.qml"
        case "metadata":
            return "pages/MetadataPage.qml"
        case "lyricsCover":
            return "pages/LyricsCoverPage.qml"
        case "analysis":
            return "pages/AnalysisPage.qml"
        case "settings":
            return "pages/SettingsPage.qml"
        default:
            return "pages/AutoConvertPage.qml"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TopStatusBar {
            Layout.fillWidth: true
            theme: theme
            typography: typography
            appName: appState.appName
            moduleName: appState.currentModuleName
            statusSummary: appState.statusSummary
            modeLabel: capabilityGate.previewMode ? "预览模式" : "正常运行"
            capabilityLabel: capabilityGate.previewMode ? "" : root.userFeatureSummary()
            versionLabel: appState.versionLabel
            inspectorVisible: root.inspectorPanelVisible
            inspectorCanToggle: !root.inspectorTemporarilyCollapsed
            onInspectorToggleRequested: {
                if (root.inspectorPanelVisible) {
                    root.inspectorUserCollapsed = true
                } else if (!root.inspectorTemporarilyCollapsed) {
                    root.inspectorUserCollapsed = false
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            SidebarNavigation {
                id: sidebarNavigation
                Layout.fillHeight: true
                theme: theme
                typography: typography
                modules: root.modules
                currentModuleKey: appState.currentModuleKey
                onModuleRequested: function(moduleKey) {
                    appState.switchModule(moduleKey)
                }
            }

            Rectangle {
                Layout.minimumWidth: 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: theme.surface
                border.color: theme.border
                border.width: 1

                Loader {
                    id: pageLoader
                    anchors.fill: parent
                    anchors.margins: theme.spacing
                    source: root.currentPageSource
                    opacity: status === Loader.Ready ? 1.0 : 0.0

                    Behavior on opacity {
                        NumberAnimation { duration: theme.durationNormal }
                    }

                    onLoaded: {
                        item.theme = theme
                        item.typography = typography
                        if (item.hasOwnProperty("fileSession")) {
                            item.fileSession = fileSessionViewModel
                        }
                        if (item.hasOwnProperty("fileBrowser")) {
                            item.fileBrowser = editorFileBrowserViewModel
                        }
                        if (item.hasOwnProperty("audioPlayer")) {
                            item.audioPlayer = audioPlayerViewModel
                        }
                        if (item.hasOwnProperty("editSession")) {
                            item.editSession = editSessionViewModel
                        }
                        if (item.hasOwnProperty("processingSession")) {
                            item.processingSession = processingSessionViewModel
                        }
                    }
                }
            }

            RightInspector {
                id: rightInspector
                Layout.fillHeight: true
                Layout.fillWidth: false
                Layout.minimumWidth: visible ? theme.inspectorMinimumWidth : 0
                Layout.preferredWidth: visible ? root.inspectorWidth : 0
                Layout.maximumWidth: visible ? theme.inspectorMaximumWidth : 0
                visible: root.inspectorPanelVisible
                theme: theme
                typography: typography
                moduleName: appState.currentModuleName
                moduleDescription: appState.currentModuleDescription
                runtimeLabel: capabilityGate.userModeLabel
                enabledFeatures: capabilityGate.enabledFeatureSummary
                safetySummary: capabilityGate.safetySummary
                actionHint: capabilityGate.previewMode ? "预览模式不会执行文件操作。" : "操作需由您手动发起。"
                fileSession: fileSessionViewModel
                audioPlayer: audioPlayerViewModel
                editSession: editSessionViewModel
                processingSession: processingSessionViewModel
            }
        }

        BottomStatusBar {
            id: bottomStatusBar
            Layout.fillWidth: true
            theme: theme
            typography: typography
            statusText: appState.statusSummary || "就绪"
            logSummary: logModel.summary
            onOpenLogRequested: root.logDrawerOpened = true
        }
    }

    LogDrawer {
        id: logDrawer
        anchors.fill: parent
        theme: theme
        typography: typography
        logModel: logModel
        opened: root.logDrawerOpened
        compactLayout: root.width < 1200
        workspaceLeftInset: sidebarNavigation.width
        workspaceRightInset: root.inspectorPanelVisible ? rightInspector.width : 0
        minimumWorkspaceWidth: root.minimumWorkspaceWidth
        onCloseRequested: {
            root.logDrawerOpened = false
            bottomStatusBar.focusLogButton()
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
            Text { text: "当前存在未导出的文件信息草稿。本次 Pitch Shift 将基于磁盘上的源文件生成，不会包含这些草稿。"; color: theme.textPrimary; font.family: typography.fontFamily; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout { Layout.fillWidth: true; Item { Layout.fillWidth: true }
                Button { text: "取消"; onClicked: processingSessionViewModel.confirmDraftWarning(false) }
                Button { text: "继续导出"; onClicked: processingSessionViewModel.confirmDraftWarning(true) }
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
                    ? "当前文件存在未导出的编辑草稿（" + editSessionViewModel.unsavedDraftLabels.join("、") + "）。是否放弃草稿并载入 “" + fileSessionViewModel.pendingFileName + "”？"
                    : "当前文件存在未导出的编辑草稿（" + editSessionViewModel.unsavedDraftLabels.join("、") + "）。是否放弃草稿并清除当前文件？"
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

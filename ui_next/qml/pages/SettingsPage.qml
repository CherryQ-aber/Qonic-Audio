import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../theme"

Item {
    id: root

    property QtObject theme: Theme {}
    property QtObject typography: Typography {}
    property var themeModeOptions: [
        {"value": "dark", "label": "深色主题"},
        {"value": "light", "label": "浅色主题"}
    ]
    property var logLevelOptions: [
        {"value": "DEBUG", "label": "Debug"},
        {"value": "INFO", "label": "Info"},
        {"value": "WARNING", "label": "Warning"},
        {"value": "ERROR", "label": "Error"}
    ]
    property var densityOptions: [
        {"value": "standard", "label": "标准"},
        {"value": "compact", "label": "紧凑"}
    ]
    property var editorFileBarModeOptions: [
        {"value": "fixed", "label": "固定"},
        {"value": "floating", "label": "悬浮（可收起）"}
    ]
    property var lyricsTimestampPrecisionOptions: [
        {"value": "millisecond", "label": "千分之一秒"},
        {"value": "centisecond", "label": "百分之一秒"}
    ]

    function optionIndex(model, value) {
        for (var index = 0; index < model.length; index += 1) {
            if (model[index].value === value) {
                return index
            }
        }
        return 0
    }

    function syncCombos() {
        targetFormatCombo.currentIndex = optionIndex(settingsViewModel.targetFormatOptions, settingsViewModel.targetFormat)
        logLevelCombo.currentIndex = optionIndex(logLevelOptions, settingsViewModel.logLevel)
        densityCombo.currentIndex = optionIndex(densityOptions, settingsViewModel.uiDensity)
        editorFileBarModeCombo.currentIndex = optionIndex(
            editorFileBarModeOptions,
            settingsViewModel.editorFileBarMode
        )
        lyricsTimestampPrecisionCombo.currentIndex = optionIndex(
            lyricsTimestampPrecisionOptions,
            settingsViewModel.lyricsTimestampPrecision
        )
    }

    function settingChanged(key) {
        var items = settingsViewModel.pendingChangeItems
        for (var index = 0; index < items.length; index += 1) {
            if (items[index].key === key)
                return true
        }
        return false
    }

    Component.onCompleted: syncCombos()

    Connections {
        target: settingsViewModel

        function onSettingsChanged() {
            syncCombos()
        }

        function onCleanupDialogRequested() {
            cleanupConfirmDialog.open()
        }
    }

        Flickable {
            id: pageScroll
            objectName: "settingsPageScroll"
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: settingsContent.implicitHeight + root.theme.spacing * 2
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ThemeScrollBar {
            theme: root.theme
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: settingsContent
            objectName: "settingsPageContent"
            // The Flickable viewport is the only page-width authority.
            // A fixed 860px content width used to extend under Inspector.
            width: pageScroll.width
            Layout.minimumWidth: 0
            spacing: theme.spacing

                Rectangle {
                    objectName: "settingsHeaderCard"
                    Layout.fillWidth: true
                    implicitHeight: headerContent.implicitHeight + theme.spacing * 2
                    color: settingsViewModel.hasPendingChanges
                        ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.08)
                        : theme.panel
                    border.color: settingsViewModel.hasPendingChanges ? theme.warning : theme.border
                    radius: theme.radiusMedium

                    ColumnLayout {
                        id: headerContent
                        anchors.fill: parent
                        anchors.margins: theme.spacing + 4
                        spacing: theme.spacing

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Text {
                                text: "设置"
                                color: theme.textPrimary
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeTitle
                                font.weight: typography.weightBold
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }

                            Text {
                                visible: settingsViewModel.saveStatus.length > 0
                                text: settingsViewModel.saveStatus
                                color: theme.textSecondary
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeSmall
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }

                        Text {
                            visible: settingsViewModel.hasPendingChanges
                            text: settingsViewModel.draftStateText
                            color: theme.warning
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeBody
                            font.weight: typography.weightBold
                            Layout.fillWidth: true
                        }

                        ColumnLayout {
                            visible: settingsViewModel.hasPendingChanges
                            Layout.fillWidth: true
                            spacing: 5

                            Repeater {
                                model: settingsViewModel.pendingChangeItems

                                RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: modelData.label
                                        color: theme.textPrimary
                                        font.family: typography.fontFamily
                                        font.pixelSize: typography.sizeSmall
                                        Layout.preferredWidth: 130
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: modelData.before + "  →  " + modelData.after
                                        color: theme.textSecondary
                                        font.family: typography.fontFamily
                                        font.pixelSize: typography.sizeSmall
                                        Layout.fillWidth: true
                                        elide: Text.ElideMiddle
                                    }
                                    StatusBadge {
                                        visible: modelData.automaticConversion
                                        theme: root.theme
                                        typography: root.typography
                                        label: "自动转码"
                                        tone: "warning"
                                    }
                                }
                            }
                        }

                        Text {
                            visible: settingsViewModel.hasAutoConvertChanges
                                && settingsViewModel.autoConvertBusy
                            text: settingsViewModel.applyBlockedReason
                            color: theme.warning
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Flow {
                            objectName: "settingsDraftActions"
                            Layout.fillWidth: true
                            spacing: 8
                            SettingsButton { theme: root.theme; typography: root.typography; label: "放弃修改"; preferredWidth: 112; enabled: settingsViewModel.hasPendingChanges; onClicked: settingsViewModel.discardPendingChanges() }
                            SettingsButton { theme: root.theme; typography: root.typography; label: "重新载入"; preferredWidth: 112; enabled: !settingsViewModel.hasPendingChanges; disabledReason: "请先应用或放弃当前修改。"; onClicked: settingsViewModel.reloadConfig() }
                            SettingsButton { theme: root.theme; typography: root.typography; label: "应用修改"; preferredWidth: 156; tone: "warning"; enabled: settingsViewModel.canApplyPendingChanges; disabledReason: settingsViewModel.applyBlockedReason; onClicked: settingsViewModel.savePendingChanges() }
                        }
                    }
                }

                GridLayout {
                    id: settingsSectionsGrid
                    objectName: "settingsSectionsGrid"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    columns: width >= 900 ? 2 : 1
                    columnSpacing: theme.spacing
                    rowSpacing: theme.spacing

                SettingSection {
                    objectName: "settingsPathSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "路径设置"
                    subtitle: "选择新路径后，需在页面顶部确认应用。"
                    statusLabel: root.settingChanged("watch_folder")
                        || root.settingChanged("output_folder")
                        || root.settingChanged("editor_output_folder") ? "未保存" : ""
                    statusTone: "warning"

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "监听目录"
                        path: settingsViewModel.watchFolder
                        helperText: "自动转码监听的来源目录。"
                        draftOnly: true
                        browseEnabled: true
                        onBrowseRequested: settingsViewModel.choosePendingWatchFolder()
                    }

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "转码输出"
                        path: settingsViewModel.outputFolder
                        helperText: "自动转码生成文件的默认目录。"
                        draftOnly: true
                        browseEnabled: true
                        onBrowseRequested: settingsViewModel.choosePendingOutputFolder()
                    }

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "编辑输出"
                        path: settingsViewModel.editorOutputFolder
                        helperText: "音频编辑导出时使用的默认目录。"
                        draftOnly: true
                        browseEnabled: true
                        onBrowseRequested: settingsViewModel.choosePendingEditorOutputFolder()
                    }

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "缓存目录"
                        path: settingsViewModel.cacheFolder
                        browseEnabled: false
                        helperText: "程序临时缓存位置；清理功能位于“日志与缓存”。"
                    }
                }

                SettingSection {
                    objectName: "settingsAutoConvertSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "自动转码设置"
                    subtitle: "修改需确认后生效；转换进行中不可应用，已创建任务保留原参数。"
                    statusLabel: settingsViewModel.hasAutoConvertChanges ? "未保存" : ""
                    statusTone: "warning"

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "默认输出格式"

                        FormatSelector {
                            id: targetFormatCombo
                            Layout.preferredWidth: 280
                            theme: root.theme
                            typography: root.typography
                            options: settingsViewModel.targetFormatOptions
                            value: settingsViewModel.targetFormat
                            onFormatSelected: settingsViewModel.updatePendingValue("target_format", value)
                        }
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "启动后自动监听"
                        helperText: "应用后在下次启动时自动开启目录监听。"
                        checked: settingsViewModel.autoStartMonitor
                        onToggled: settingsViewModel.updatePendingValue("auto_start_monitor", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "启动监听时扫描已有文件"
                        helperText: "启动监听时将目录内已有文件加入扫描。"
                        checked: settingsViewModel.scanExistingOnStart
                        onToggled: settingsViewModel.updatePendingValue("scan_existing_on_start", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "按目标格式创建子文件夹"
                        helperText: "在输出目录下按格式创建分类子目录。"
                        checked: settingsViewModel.createFormatSubfolder
                        onToggled: settingsViewModel.updatePendingValue("create_format_subfolder", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "保持输入目录结构"
                        helperText: "在输出目录中保留来源文件的相对目录层级。"
                        checked: settingsViewModel.preserveRelativeStructure
                        onToggled: settingsViewModel.updatePendingValue("preserve_relative_structure", checked)
                    }

                    Text {
                        text: "源文件处理方式：保留源文件（本轮固定，不提供删除源文件选项）。"
                        color: theme.textSecondary
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }

                SettingSection {
                    objectName: "settingsLyricsSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "歌词设置"
                    subtitle: "修改会保存在当前设置草稿中，确认后应用。"
                    statusLabel: root.settingChanged("lyrics_timestamp_precision")
                        || root.settingChanged("embed_lyrics_after_convert")
                        || root.settingChanged("copy_lrc_to_output")
                        || root.settingChanged("overwrite_existing_lyrics") ? "未保存" : ""
                    statusTone: "warning"

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "时间点精度"

                        FormatSelector {
                            id: lyricsTimestampPrecisionCombo
                            objectName: "lyricsTimestampPrecisionCombo"
                            Layout.preferredWidth: 220
                            theme: root.theme
                            typography: root.typography
                            options: lyricsTimestampPrecisionOptions
                            value: settingsViewModel.lyricsTimestampPrecision
                            onFormatSelected: settingsViewModel.setLyricsTimestampPrecision(value)
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "千分之一秒示例 [03:21.450]；百分之一秒示例 [03:21.45]。"
                            color: theme.muted
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            wrapMode: Text.WordWrap
                        }
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "转换后写入内嵌歌词"
                        helperText: "转码完成后将歌词写入支持的音频容器。"
                        checked: settingsViewModel.embedLyricsAfterConvert
                        onToggled: settingsViewModel.updatePendingValue("embed_lyrics_after_convert", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "同时保留外置 .lrc"
                        helperText: "转码输出旁同时保留同名 .lrc 文件。"
                        checked: settingsViewModel.copyLrcToOutput
                        onToggled: settingsViewModel.updatePendingValue("copy_lrc_to_output", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "覆盖已有歌词"
                        helperText: "写入时允许替换输出文件内已有的歌词标签。"
                        checked: settingsViewModel.overwriteExistingLyrics
                        danger: true
                        onToggled: settingsViewModel.updatePendingValue("overwrite_existing_lyrics", checked)
                    }
                }

                SettingSection {
                    objectName: "settingsPlaybackSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "播放设置"
                    subtitle: "当前由系统管理音频输出设备。"

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "输出设备"

                        Rectangle {
                            Layout.preferredWidth: 320
                            implicitHeight: 30
                            color: theme.surface
                            border.color: theme.border
                            radius: theme.radiusSmall

                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: Text.AlignVCenter
                                text: settingsViewModel.audioOutputDeviceName
                                color: theme.textSecondary
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeSmall
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }

                    }
                }

                SettingSection {
                    objectName: "settingsThemeSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "主题与界面"
                    subtitle: "主题可立即预览；确认应用后保留为下次启动设置。"
                    statusLabel: root.settingChanged("theme_mode")
                        || root.settingChanged("ui_density")
                        || root.settingChanged("editor_file_bar_mode") ? "未保存" : ""
                    statusTone: "warning"

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "主题模式"

                        FormatSelector {
                            id: themeModeCombo
                            Layout.preferredWidth: 220
                            theme: root.theme
                            typography: root.typography
                            options: themeModeOptions
                            value: theme.mode
                            onFormatSelected: theme.setMode(value)
                        }

                        Text {
                            text: "仅本次运行生效"
                            color: theme.muted
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                        }
                    }

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "UI 密度"

                        FormatSelector {
                            id: densityCombo
                            Layout.preferredWidth: 220
                            theme: root.theme
                            typography: root.typography
                            options: densityOptions
                            value: settingsViewModel.uiDensity
                            onFormatSelected: settingsViewModel.updatePendingValue("ui_density", value)
                        }
                    }

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "公共文件栏"

                        FormatSelector {
                            id: editorFileBarModeCombo
                            objectName: "editorFileBarModeCombo"
                            Layout.preferredWidth: 220
                            theme: root.theme
                            typography: root.typography
                            options: editorFileBarModeOptions
                            value: settingsViewModel.editorFileBarMode
                            onFormatSelected: settingsViewModel.setEditorFileBarMode(value)
                        }

                        Text {
                            text: "切换后立即预览；固定模式保留当前布局，悬浮模式默认藏在顶部，通过“编辑页面”行右侧按钮展开。保存确认后作为下次启动默认值。"
                            color: theme.muted
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                SettingSection {
                    objectName: "settingsLogCacheSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "日志与缓存"
                    subtitle: "显示当前磁盘占用；清理前会先列出文件或缓存分类。"
                    statusLabel: settingsViewModel.storageBusy ? "读取中" : ""
                    statusTone: "muted"

                    SettingRow {
                        theme: root.theme
                        typography: root.typography
                        label: "日志级别"

                        FormatSelector {
                            id: logLevelCombo
                            Layout.preferredWidth: 220
                            theme: root.theme
                            typography: root.typography
                            options: logLevelOptions
                            value: settingsViewModel.logLevel
                            onFormatSelected: settingsViewModel.updatePendingValue("log_level", value)
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 62
                        color: theme.surface
                        border.color: theme.border
                        radius: theme.radiusSmall

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text { text: "日志"; color: theme.textPrimary; font.family: typography.fontFamily; font.pixelSize: typography.sizeBody; font.weight: typography.weightBold }
                                Text { text: settingsViewModel.logFileCount + " 个文件"; color: theme.textSecondary; font.family: typography.fontFamily; font.pixelSize: typography.sizeSmall }
                            }
                            Text { text: settingsViewModel.logUsageText; color: theme.accent; font.family: typography.fontFamily; font.pixelSize: typography.sizeMedium; font.weight: typography.weightBold }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 62
                        color: theme.surface
                        border.color: theme.border
                        radius: theme.radiusSmall

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text { text: "缓存"; color: theme.textPrimary; font.family: typography.fontFamily; font.pixelSize: typography.sizeBody; font.weight: typography.weightBold }
                                Text { text: settingsViewModel.cacheFileCount + " 个文件"; color: theme.textSecondary; font.family: typography.fontFamily; font.pixelSize: typography.sizeSmall }
                            }
                            Text { text: settingsViewModel.cacheUsageText; color: theme.accent; font.family: typography.fontFamily; font.pixelSize: typography.sizeMedium; font.weight: typography.weightBold }
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "打开日志位置"
                            onClicked: settingsViewModel.openLogFolder()
                        }

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "复制最近日志"
                            onClicked: settingsViewModel.copyRecentLogs()
                        }

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "清理日志"
                            tone: "warning"
                            enabled: settingsViewModel.canPrepareLogCleanup
                            disabledReason: settingsViewModel.storageBusy ? "正在读取占用空间。" : "当前没有可清理的日志。"
                            onClicked: settingsViewModel.prepareLogCleanup()
                        }

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "清理缓存"
                            preferredWidth: 128
                            tone: "warning"
                            enabled: settingsViewModel.canPrepareCacheCleanup
                            disabledReason: settingsViewModel.cacheCleanupBlocked
                                ? settingsViewModel.cacheCleanupBlockedReason
                                : settingsViewModel.storageBusy
                                    ? "正在读取占用空间。"
                                    : "当前没有可清理的缓存。"
                            onClicked: settingsViewModel.prepareCacheCleanup()
                        }

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "刷新占用"
                            enabled: !settingsViewModel.storageBusy
                            onClicked: settingsViewModel.refreshStorageUsage()
                        }
                    }
                }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 8
                }
        }
    }

    Dialog {
        id: cleanupConfirmDialog
        objectName: "settingsStorageCleanupDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(620, root.width - root.theme.spacing * 4)
        modal: true
        title: settingsViewModel.cleanupTitle
        standardButtons: Dialog.NoButton
        closePolicy: Popup.CloseOnEscape
        onClosed: {
            if (settingsViewModel.cleanupTarget.length > 0)
                settingsViewModel.cancelPreparedCleanup()
        }

        background: Rectangle {
            color: root.theme.panel
            border.color: root.theme.border
            radius: root.theme.radiusMedium
        }

        contentItem: ColumnLayout {
            spacing: root.theme.spacing

            Text {
                text: settingsViewModel.cleanupSummary
                color: root.theme.textPrimary
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeBody
                font.weight: root.typography.weightBold
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            ScrollView {
                id: cleanupScroll
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(260, cleanupList.implicitHeight)
                clip: true

                ColumnLayout {
                    id: cleanupList
                    width: cleanupScroll.availableWidth
                    spacing: 6

                    Repeater {
                        model: settingsViewModel.cleanupItems

                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: 58
                            color: root.theme.surface
                            border.color: root.theme.border
                            radius: root.theme.radiusSmall

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 10

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { text: modelData.label; color: root.theme.textPrimary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeBody; Layout.fillWidth: true; elide: Text.ElideRight }
                                    Text { text: modelData.detail; color: root.theme.textSecondary; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeTiny; Layout.fillWidth: true; elide: Text.ElideMiddle }
                                }
                                Text { text: modelData.sizeText; color: root.theme.warning; font.family: root.typography.fontFamily; font.pixelSize: root.typography.sizeSmall; font.weight: root.typography.weightBold }
                            }
                        }
                    }
                }
            }

            Text {
                text: "确认后将删除上列程序日志或临时缓存，此操作不可撤回。"
                color: root.theme.warning
                font.family: root.typography.fontFamily
                font.pixelSize: root.typography.sizeSmall
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                SettingsButton {
                    theme: root.theme
                    typography: root.typography
                    label: "取消"
                    preferredWidth: 96
                    onClicked: {
                        settingsViewModel.cancelPreparedCleanup()
                        cleanupConfirmDialog.close()
                    }
                }
                SettingsButton {
                    theme: root.theme
                    typography: root.typography
                    label: "确认清理"
                    preferredWidth: 112
                    tone: "error"
                    onClicked: {
                        settingsViewModel.confirmPreparedCleanup()
                        cleanupConfirmDialog.close()
                    }
                }
            }
        }
    }

    component SettingRow: ColumnLayout {
        property QtObject theme
        property QtObject typography
        property string label: ""

        Layout.fillWidth: true
        spacing: theme.spacing

        Text {
            text: label
            color: theme.textPrimary
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeBody
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    component SettingsCheckBox: CheckBox {
        property QtObject theme
        property QtObject typography
        property string label: ""
        property bool danger: false

        Layout.fillWidth: true
        text: label
        spacing: 9
        font.family: typography.fontFamily
        font.pixelSize: typography.sizeBody

        contentItem: Text {
            text: parent.text
            color: !parent.enabled ? theme.textDisabled : parent.danger ? theme.warning : theme.textPrimary
            font: parent.font
            verticalAlignment: Text.AlignVCenter
            leftPadding: parent.indicator.width + parent.spacing
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        indicator: Rectangle {
            implicitWidth: 18
            implicitHeight: 18
            x: parent.leftPadding
            y: parent.topPadding + (parent.availableHeight - height) / 2
            color: !parent.enabled ? theme.disabledBackground : parent.checked ? theme.selectedBackground : theme.inputBackground
            border.color: parent.visualFocus ? theme.focusRing : !parent.enabled ? theme.borderSubtle : parent.danger ? theme.warning : parent.checked ? theme.selectedIndicator : theme.borderNormal
            border.width: parent.visualFocus ? 2 : 1
            radius: theme.radiusSmall

            Rectangle {
                anchors.centerIn: parent
                width: 8
                height: 8
                visible: parent.parent.checked
                color: !parent.parent.enabled ? theme.textDisabled : parent.parent.danger ? theme.warning : theme.selectedIndicator
                radius: 1
            }
        }
    }

    component SettingsButton: WorkstationButton {
        property string label: ""
        property int preferredWidth: 128

        objectName: "settingsActionButton"
        width: preferredWidth
        implicitWidth: preferredWidth
        Layout.preferredWidth: preferredWidth
        theme: root.theme
        typography: root.typography
        text: label
        disabledReason: "当前设置在此状态下不可用。"
    }

    component DraftSettingBlock: Rectangle {
        property QtObject theme
        property QtObject typography
        property string label: ""
        property string helperText: ""
        property bool checked: false
        property bool danger: false

        signal toggled(bool checked)

        Layout.fillWidth: true
        implicitHeight: draftBlockContent.implicitHeight + 9
        color: danger
            ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.09)
            : theme.surface
        border.color: danger ? theme.warning : theme.border
        radius: theme.radiusSmall

        ColumnLayout {
            id: draftBlockContent
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            anchors.topMargin: 4
            anchors.bottomMargin: 5
            spacing: 2

            SettingsCheckBox {
                theme: parent.parent.theme
                typography: parent.parent.typography
                label: parent.parent.label
                checked: parent.parent.checked
                danger: parent.parent.danger
                onToggled: parent.parent.toggled(checked)
            }

            Text {
                text: parent.parent.helperText
                color: parent.parent.danger ? theme.warning : theme.muted
                font.family: typography.fontFamily
                font.pixelSize: typography.sizeTiny
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
    }
}

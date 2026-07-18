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
    }

    Component.onCompleted: syncCombos()

    Connections {
        target: settingsViewModel

        function onSettingsChanged() {
            syncCombos()
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
                    color: Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.08)
                    border.color: settingsViewModel.previewMode ? theme.warning : theme.accent
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
                                text: settingsViewModel.previewMode
                                    ? settingsViewModel.previewSafetyMessage
                                    : "设置修改会先进入页面草稿，只有确认后才写入 config.json。"
                                color: settingsViewModel.previewMode ? theme.warning : theme.accent
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeBody
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                            }

                            Text {
                                text: settingsViewModel.saveStatus
                                color: theme.textSecondary
                                font.family: typography.fontFamily
                                font.pixelSize: typography.sizeSmall
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }

                        DraftStatusBadge {
                            theme: root.theme
                            typography: root.typography
                            hasChanges: settingsViewModel.hasPendingChanges
                            previewMode: settingsViewModel.previewMode
                            Layout.alignment: Qt.AlignLeft
                        }

                        Text {
                            text: settingsViewModel.draftStateText
                            color: settingsViewModel.hasPendingChanges ? theme.warning : theme.textSecondary
                            font.family: typography.fontFamily
                            font.pixelSize: typography.sizeSmall
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                        }

                        Flow {
                            objectName: "settingsDraftActions"
                            Layout.fillWidth: true
                            spacing: 8
                            SettingsButton { theme: root.theme; typography: root.typography; label: settingsViewModel.previewMode ? "模拟保存草稿" : "检查当前草稿"; preferredWidth: 142; enabled: settingsViewModel.hasPendingChanges; onClicked: settingsViewModel.simulateSaveDraft() }
                            SettingsButton { theme: root.theme; typography: root.typography; label: "放弃草稿"; preferredWidth: 104; enabled: settingsViewModel.hasPendingChanges; onClicked: settingsViewModel.discardPendingChanges() }
                            SettingsButton { theme: root.theme; typography: root.typography; label: "重新读取真实配置"; preferredWidth: 154; onClicked: settingsViewModel.reloadConfig() }
                            SettingsButton { theme: root.theme; typography: root.typography; label: "保存设置"; preferredWidth: 218; tone: settingsViewModel.previewMode ? "warning" : "error"; enabled: settingsViewModel.canPersistConfig && settingsViewModel.hasPendingChanges; disabledReason: settingsViewModel.previewMode ? "预览模式不会写入配置。" : "当前无需要保存的草稿。"; onClicked: settingsViewModel.savePendingChanges() }
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
                    subtitle: settingsViewModel.previewMode ? "所有路径仅为页面草稿，不写入 config.json，也不会改变旧 Widgets UI 或后台任务使用的目录。" : "路径选择先进入页面草稿，保存并确认后才写入 config.json。"
                    statusLabel: settingsViewModel.previewMode ? "草稿不生效" : "待确认后保存"
                    statusTone: settingsViewModel.previewMode ? "warning" : "accent"

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "监听目录"
                        path: settingsViewModel.watchFolder
                        helperText: "页面草稿：当前不会改变后台监听目录。"
                        draftOnly: true
                        browseEnabled: true
                        onBrowseRequested: settingsViewModel.choosePendingWatchFolder()
                    }

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "转码输出"
                        path: settingsViewModel.outputFolder
                        helperText: "页面草稿：当前不会改变后台转码输出目录。"
                        draftOnly: true
                        browseEnabled: true
                        onBrowseRequested: settingsViewModel.choosePendingOutputFolder()
                    }

                    PathField {
                        theme: root.theme
                        typography: root.typography
                        label: "编辑输出"
                        path: settingsViewModel.editorOutputFolder
                        helperText: "页面草稿：当前不会改变旧 Widgets UI 的音频编辑输出目录。"
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
                        helperText: "只读占位；当前不提供清理操作。"
                        tone: "warning"
                    }
                }

                SettingSection {
                    objectName: "settingsAutoConvertSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "自动转码设置"
                    subtitle: settingsViewModel.previewMode ? "草稿不生效：仅更新本页内容，不会写入 config.json，也不会启动、停止或改变后台任务。" : "设置只更新草稿，点击保存并确认后才写入 config.json。"
                    statusLabel: settingsViewModel.previewMode ? "不影响后台任务" : "待确认草稿"
                    statusTone: settingsViewModel.previewMode ? "warning" : "accent"

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
                        helperText: "草稿项，当前不会启动监听或影响旧 Widgets UI。"
                        checked: settingsViewModel.autoStartMonitor
                        onToggled: settingsViewModel.updatePendingValue("auto_start_monitor", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "启动监听时扫描已有文件"
                        helperText: "草稿项，当前不会扫描目录或改变后台队列。"
                        checked: settingsViewModel.scanExistingOnStart
                        onToggled: settingsViewModel.updatePendingValue("scan_existing_on_start", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "按目标格式创建子文件夹"
                        helperText: "草稿项，当前不会改变后台输出目录结构。"
                        checked: settingsViewModel.createFormatSubfolder
                        onToggled: settingsViewModel.updatePendingValue("create_format_subfolder", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "保持输入目录结构"
                        helperText: "仅影响保存后新加入的 QML 批量任务；已有任务保留创建时的参数快照。"
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
                    subtitle: settingsViewModel.previewMode ? "歌词选项均为页面草稿；不会写入 config.json、不会接入转换流程，也不会修改音频或 .lrc。" : "保存并确认后才可能影响后续转换配置。"
                    statusLabel: settingsViewModel.previewMode ? "预览时不生效" : "待确认草稿"
                    statusTone: "warning"

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "转换后写入内嵌歌词"
                        helperText: "草稿项，当前不会接入转换流程。"
                        checked: settingsViewModel.embedLyricsAfterConvert
                        onToggled: settingsViewModel.updatePendingValue("embed_lyrics_after_convert", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "同时保留外置 .lrc"
                        helperText: "草稿项，当前仅用于 UI 预览。"
                        checked: settingsViewModel.copyLrcToOutput
                        onToggled: settingsViewModel.updatePendingValue("copy_lrc_to_output", checked)
                    }

                    DraftSettingBlock {
                        theme: root.theme
                        typography: root.typography
                        label: "覆盖已有歌词"
                        helperText: "草稿项；覆盖已有歌词的功能暂未开放。"
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
                    subtitle: "设备设置占位，当前不会切换播放设备。WASAPI / WaveOut / ASIO 均未接入。"
                    statusLabel: "设备设置占位"
                    statusTone: "muted"

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

                        StatusBadge {
                            theme: root.theme
                            typography: root.typography
                            label: "只读占位"
                            tone: "muted"
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        StatusBadge {
                            theme: root.theme
                            typography: root.typography
                            label: "WASAPI 预留"
                            tone: "muted"
                        }

                        StatusBadge {
                            theme: root.theme
                            typography: root.typography
                            label: "WaveOut 预留"
                            tone: "muted"
                        }

                        StatusBadge {
                            theme: root.theme
                            typography: root.typography
                            label: "ASIO 待接入"
                            tone: "warning"
                        }
                    }

                    Text {
                        text: "设备设置占位，当前不会切换播放设备。"
                        color: theme.muted
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        Layout.fillWidth: true
                    }
                }

                SettingSection {
                    objectName: "settingsThemeSection"
                    Layout.alignment: Qt.AlignTop
                    theme: root.theme
                    typography: root.typography
                    title: "主题与界面"
                    subtitle: "主题切换只作用于本次 QML 运行会话。UI 密度和公共文件栏布局先进入页面草稿。"
                    statusLabel: "会话内生效"
                    statusTone: "muted"

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
                    subtitle: "日志级别只进入页面草稿；缓存清理功能暂未开放。"
                    statusLabel: "缓存清理禁用"
                    statusTone: "warning"

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

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "打开日志位置"
                            enabled: false
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
                            label: "清空日志抽屉"
                            tone: "warning"
                            onClicked: settingsViewModel.clearLogPreview()
                        }

                        SettingsButton {
                            theme: root.theme
                            typography: root.typography
                            label: "清理缓存（当前不可用）"
                            preferredWidth: 184
                            tone: "error"
                            enabled: false
                        }
                    }

                    Text {
                        text: "当前不提供缓存清理操作。"
                        color: theme.warning
                        font.family: typography.fontFamily
                        font.pixelSize: typography.sizeSmall
                        Layout.fillWidth: true
                    }
                }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 8
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

    component DraftStatusBadge: Rectangle {
        property QtObject theme
        property QtObject typography
        property bool hasChanges: false
        property bool previewMode: true

        Layout.preferredWidth: 172
        implicitHeight: 34
        color: hasChanges
            ? Qt.rgba(theme.warning.r, theme.warning.g, theme.warning.b, 0.12)
            : Qt.rgba(theme.success.r, theme.success.g, theme.success.b, 0.10)
        border.color: hasChanges ? theme.warning : theme.success
        radius: theme.radiusSmall

        Text {
            anchors.centerIn: parent
            text: hasChanges
                ? (previewMode ? "草稿未写入磁盘" : "等待保存确认")
                : "当前无草稿修改"
            color: hasChanges ? theme.warning : theme.success
            font.family: typography.fontFamily
            font.pixelSize: typography.sizeSmall
            font.weight: typography.weightMedium
            elide: Text.ElideRight
            maximumLineCount: 1
        }
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

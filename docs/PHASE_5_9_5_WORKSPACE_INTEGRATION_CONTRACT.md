# Phase 5.9.5 QML 工作分区整合实施契约

## 1. 文档状态

- 日期：2026-07-18
- 项目：CherryQ Audio Converter v5.0 Internal Test
- 阶段：Phase 5.9.5-A
- 状态：PlayerSession 与媒体事务安全基础已实现、通过回归并完成提交收尾
- 下一阶段：等待用户明确要求继续 Phase 5.9.5-B
- 长期计划：`Codex_memory/PHASE_5_9_5_WORKSPACE_INTEGRATION_PLAN.md`

本文是 Phase 5.9.5 的工程合同。长期计划描述完整方向，本文固定当前代码基线、状态归属、兼容规则、测试迁移和阶段门禁。后续实现如需改变本文合同，必须先更新本文并单独汇报，不得在代码修改中隐式改变语义。

## 2. Phase 5.9.5-0 实测基线

### 2.1 Git 与运行环境

| 项目 | 基线 |
|---|---|
| 分支 | `codex/v5_P1` |
| HEAD | `37b74d5c02558d6c3ed540e9b7b800320aff3641` |
| Python | 3.12.1 |
| PySide6 | 6.11.1 |
| Qt | 6.11.1 |
| FFmpeg | 8.1.1 full build |
| `config.json` SHA256 | `EA8BE86CDF7FC7C9351B7F961D9D8B9BC97AD3D414FB7B6A8B8376B8E82CA72B` |
| `config.json.bak` SHA256 | `CBED09046D02FC40A229CED3D9BD0E8642F80C13185B1AED3862BB44ED14B1E4` |

配置哈希只记录本次基线，不得写成永久固定断言。每个阶段都应重新计算操作前后哈希。

### 2.2 自动化与兼容入口

| 验证 | 结果 |
|---|---|
| 完整回归 | `460 passed, 2 warnings, 20 subtests passed` |
| Phase A 候选专项 | `45 passed, 2 subtests passed` |
| 默认 QML smoke | 通过 |
| `autoConvert` smoke | 通过 |
| `audioEditor` smoke | 通过 |
| `metadata` smoke | 通过 |
| `lyricsCover` smoke | 通过 |
| `analysis` smoke | 通过 |
| `settings` 模块键 smoke | 通过 |
| `--qml-open-settings` smoke | 通过 |
| Legacy `gui` / `MainWindow` import | 通过 |
| smoke 前后 `config.json` | SHA256 不变 |
| 核心候选文件 `git diff --check` | 通过 |

现有两条 warning 均来自 `tests/test_release_baseline.py` 中 Qt `QMouseEvent` 旧构造函数的弃用提示。Phase 5.9.5 不扩大允许 warning 集合。

### 2.3 进程基线

验证结束后检测到一个既有进程：

```text
python.exe main_qml.py
PID 23940
启动时间 2026-07-18 14:53:38 +08:00
```

该进程命令行不含本阶段 smoke 参数，未由本阶段测试强制终止。进入 Phase 5.9.5-A 的真实媒体锁和释放测试前必须重新检查；未经用户确认不得结束可能属于用户的交互式程序。

## 3. 脏工作树保护合同

Phase 5.9.5-0 开始时：

- 已暂存路径：147
- 未暂存路径：86
- 未跟踪路径：415

未跟踪数量包含既有审查包、许可证、阶段文档和测试文件。以上内容均视为用户或前序阶段资产，不得批量清理。

Phase A 的全部候选生产文件和多数测试已经是 `AM` 状态；`tests/test_qml_editor_export_phase584.py` 为未跟踪文件。因此：

1. HEAD 不能单独作为 Phase 5.9.5 的差异基线。
2. 每个阶段开始前必须记录目标文件当前 SHA256。
3. 每个阶段完成后按“开始前工作副本 → 阶段后工作副本”审查，不把既有 staged 内容误报为本阶段改动。
4. 禁止：

   - `git reset --hard`
   - `git checkout --`
   - `git clean`
   - `git add .`
   - 批量覆盖或格式化既有脏文件

5. 未得到用户明确要求，不暂存、提交、推送或打包。

## 4. 工作副本哈希清单

### 4.1 Phase A 候选文件

| 文件 | SHA256 |
|---|---|
| `main_qml.py` | `C3B03235DC85508E0DB638C69511FD474B7112169206CFE585482760B8B4B652` |
| `ui_next/bridge/audio_player_viewmodel.py` | `7AFC63AA40C660D006D0FCEDC7D5F4F2EF896CDC0DA2ED9B327F766993181F74` |
| `ui_next/bridge/file_session_viewmodel.py` | `81980F9F830A4862EDA5191582538D9813F404B5AB39FE35FABA5F9797F93A2F` |
| `ui_next/bridge/edit_session.py` | `135D22F019E1FDB80C80EE9102989519B9711B70CBFC4410E264303B4D547C6D` |
| `ui_next/bridge/audio_processing_session.py` | `AD89818C270165A98DE1F624F84DB30271FA3F11F369E51F3AFEFF048AFDD2E5` |
| `tests/test_qml_audio_player.py` | `6D5CC615AB76DB0339C1079D3D161B86A047ED2A613547B0579AEBA579A30248` |
| `tests/test_qml_file_session.py` | `EF0D9FBF40A8BE5D9ACC729EB4C513C82325742FE65712901E7E5FB06E2BDAAD` |
| `tests/test_audio_processing_session.py` | `8CB88C1F3459E335710FF0812C69272C47B720011BC184CA57284E5DFB3561BC` |
| `tests/test_qml_editor_export_phase584.py` | `5F73B3E96A0AF2867545D1EE651FC02083F662A1C42F8C6D3E3590527AA321C7` |
| `tests/test_qml_unified_edit_export_dialog.py` | `E6D38334F5F377ED32DC670C38F50E00F7EC9ECCD603B72BBC0408026733E717` |

### 4.2 后续外壳与页面候选文件

| 文件 | SHA256 |
|---|---|
| `ui_next/qml/AppShell.qml` | `A8EFF0534890515C464B9B3473463D2540566742F02EBA60E13BC63D87A62184` |
| `ui_next/bridge/app_state_viewmodel.py` | `DB575C59BCB4BDFA89C52200A97AC4CC582CF4C485938AD307936230E4D7DC69` |
| `ui_next/bridge/task_queue_model.py` | `9D1B341971861E8F9ECA3332A3781169302343A1C64CDCD4A0AD0E411940906F` |
| `ui_next/bridge/auto_convert_viewmodel.py` | `D7F7DB56597188D34D93D01EE93A79E9F21C3742D5312300797980B09E51203E` |
| `ui_next/qml/pages/AutoConvertPage.qml` | `6782AFBFCBB79E3DC89D4678D6E9CEBEA33B79E0DF7325BFBC9441A52F172F79` |
| `ui_next/qml/pages/AudioEditorPage.qml` | `1841E5DC1073CFF7C84AF611F2582976EF08FFF5A8C513DE9BE49C5809B7DCC9` |
| `ui_next/qml/pages/MetadataPage.qml` | `0B0D8E1165DE44CB80F6F07064A97811EA7C8E21106C0C9EF5B480DE963E0998` |
| `ui_next/qml/pages/LyricsCoverPage.qml` | `7A23D1C8994DD98868D4B25FF0CEB8A8FA760CD057532446BB3DB662040D7522` |
| `ui_next/qml/pages/AudioProcessingPage.qml` | `4A9B94B982BA3D5D7AAE4F6B46CA64E339F32040F0CD5F59E18DF9DC16FDAF50` |
| `ui_next/qml/pages/SettingsPage.qml` | `736905B3C93E2F414E5EE6D7C3D023A70CED0D2B7CA75D864B4E5102722C46FA` |
| `ui_next/qml/components/TaskQueueView.qml` | `DA5ACA4D47A38F0EEBAB22486C8BBE5C14D09BE08E1CC2A0B60ED6E7B6F1B9D6` |
| `ui_next/qml/components/TaskRowDelegate.qml` | `9E6FCEF2014769A2B6140211C4E6774B0F8382588E99EB6220B7884189513101` |
| `ui_next/qml/components/CurrentFileBar.qml` | `3E8FF0707CC09B50E9C085A50F55C1A9D20F526F38C774A682BEE36091E0F0A1` |
| `ui_next/qml/components/PlayerBar.qml` | `03038C0FB269EBA758DB80A2F2C8D9EA9847D0FB9211C058B471CEAF7876E908` |
| `ui_next/qml/components/LyricsDraftEditor.qml` | `F89AFD49597EB079F006034EF11EE2D0DF2C90260EB15A63C38DC8DC42FCAE68` |

若文件哈希在下一阶段开始前发生变化，必须先重新读取并更新阶段基线，不能按本文旧哈希覆盖新内容。

## 5. 对象所有权与生命周期

| 状态/资源 | 唯一所有者 | 页面切换 |
|---|---|---|
| watcher 任务 | `watcher` | 保持 |
| 任务展示 | `TaskQueueModel` | 保持 |
| 自动转码控制 | `AutoConvertViewModel` | 保持 |
| 当前编辑文件 | `FileSessionViewModel` | 保持 |
| Metadata/Cover/Lyrics 草稿 | `EditSessionViewModel` | 保持 |
| Pitch 参数、试听缓存、正式导出 | `ProcessingSessionViewModel` | 保持 |
| QMediaPlayer/QAudioOutput | `AudioPlayerViewModel` | 保持 |
| 设置 pending 草稿 | `SettingsViewModel` | 保持 |
| 日志数据 | `LogModel` | 保持 |
| 编辑正式导出对话框 | AppShell 中唯一 `EditExportDialog` | 保持 |
| 队列选择/滚动 | 持久化 AutoConvertWorkspace QML 实例 | 保持 |
| 歌词光标/选区/滚动 | 持久化 Lyrics 页面 QML 实例 | 保持 |

禁止重新注入旧 `EditorSessionViewModel`，禁止创建第二个 PlayerSession、TaskQueueModel、EditSession 或 EditExportDialog。

## 6. 工作区和兼容路由

正式导航只有两个一级工作区：

```text
autoConvert
audioEditor
```

音频编辑二级页：

```text
fileInfo
lyrics
audioProcessing
```

自动转码二级状态：

```text
all
waiting
processing
excluded
completed
failed
```

既有模块键与新增兼容键映射：

| 入口 | 入口类型 | 新状态 |
|---|---|---|
| `autoConvert` | 既有模块键 | 自动转码 / `all` |
| `audioEditor` | 既有模块键 | 音频编辑 / `fileInfo` |
| `metadata` | 既有模块键 | 音频编辑 / `fileInfo` |
| `lyricsCover` | 既有模块键 | 音频编辑 / `lyrics` |
| `audioProcessing` | Phase 5.9.5 新增兼容键 | 音频编辑 / `audioProcessing` |
| `settings` | 既有模块键 | 打开设置 Overlay；启动底层为默认 `autoConvert` |
| `analysis` | 既有模块键 | 隐藏 Legacy 兼容页，不出现在正式导航 |
| `--qml-open-settings` | 既有命令行入口 | 打开设置 Overlay；启动底层为默认 `autoConvert` |

未知键继续产生明确错误，不静默映射到首页。

### 运行模式与能力优先级

工作区重组不得改变 `main_qml.py` 的能力选择顺序：

```text
--qml-smoke-test
→ --preview
→ CHERRYQ_QML_USER_TEST=1
→ CHERRYQ_QML_CAPS
→ 默认用户能力
```

- `CHERRYQ_QML_LIVE=1` 单独存在时仍不授予能力；
- 主题选择独立于 capability，不得成为能力旁路；
- `LEGACY_SAFE` 只约束 Legacy 启动验证，不参与 QML 能力计算；
- Preview/smoke 继续禁止真实媒体读取、设备枚举、播放和写入。

## 7. 会话行为矩阵

| 操作 | PlayerSession | File/Edit/Processing |
|---|---|---|
| 切换工作区或编辑子页 | 不变 | 不变 |
| 编辑区导入文件 | 停止、载入编辑文件、位置归零 | dirty guard 后切换 |
| `reloadCurrentFile()` | 不变 | reader、EditSession、ProcessingSession 按新 generation 重新读取 |
| 清除或发现编辑文件丢失 | 无关转码播放源保持；关联的编辑文件/Pitch 源可清除 | 清除编辑会话并失效 Pitch 缓存 |
| 任务载入源文件 | 载入、不自动播放 | 不变 |
| 任务载入正式输出 | 载入、不自动播放 | 不变 |
| 任务在编辑器打开 | 用户确认后载入编辑文件 | dirty guard 后切换 |
| Pitch 缓存生成完成 | 不自动载入或播放 | FileSession 不变，只记录缓存 |
| 用户显式“播放 Pitch 试听” | 载入试听缓存，可按既有显式播放语义自动播放 | FileSession 不变 |
| 转换完成 | 不自动切换 | 不变 |
| 编辑/Pitch 导出完成 | 不自动切换 | 只记录结果 |
| 显式载入编辑/Pitch 结果 | 停止、载入结果、位置归零 | dirty guard 后切换 |
| 未来文件夹树双击 | 载入、不自动播放 | 不变 |

非编辑入口不得调用 `FileSession.setCurrentFile()`。只有“在编辑器打开”和显式载入编辑结果可以切换编辑会话。

FileSession 信号职责固定为：

- `currentFileChanged(path, generation)`：只表示当前编辑文件真实切换；
- `currentFileReloaded(path, generation)`：同一文件重新读取，不能触发播放器载入；
- `editorFilePlaybackRequested(path, generation, origin)`：真实切换后同步播放器，或用户显式重新载入同一个编辑文件时请求播放器；
- `currentFileCleared()`：清理编辑侧 reader，不得无条件清空无关转码播放源。

## 8. PlayerSession 媒体事务合同

Phase A 开始前的代码存在以下已确认风险：

1. `AudioPlayerViewModel` 直接连接 `currentFileChanged → loadFile` 和 `currentFileCleared → clear`。
2. `reloadCurrentFile()` 也发出 `currentFileChanged`。
3. `_release_snapshot` 只有一个，`prepareForFileOperation()` 可被重复调用。
4. `restorePlaybackSource()` 在无快照时回退 `currentFilePath`。
5. 编辑导出结果和 Pitch 结果载入路径会在 dirty guard 前调用播放器 prepare/release。
6. `main_qml.py` 两次调用 `setFileChangeBlocker()`，后一次覆盖前一次；该 API 不是累加器。

Phase A 必须满足：

- 只有真正切换编辑文件才请求播放器同步；
- reload 不请求播放器同步；
- 媒体文件操作非重入；
- 媒体租约期间拒绝普通播放源切换；
- restore 只接受本次有效事务；
- 无有效快照时不得回退 FileSession；
- dirty guard 取消时播放器完全不变；
- blocker 始终是一个合并谓词；
- 后端和 UI 均能读取 `mediaOperationBusy`。

媒体事务使用令牌租约：

```text
beginFileOperation(owner) -> token
finishFileOperation(token, restore=true) -> bool
```

- 同一时刻只能有一个有效 token；
- 无播放源时也允许取得租约，以保证导出锁语义一致；
- 持有租约时普通 `loadFile`/播放源切换必须拒绝；
- 错误 token、过期 token 或重复 finish 均返回失败，不能结束别人的事务；
- restore 只恢复该 token 捕获的路径和位置，不自动恢复播放；
- 没有有效快照时不得回退到 FileSession 当前文件；
- 现有 `prepareForFileOperation()` 与 `restorePlaybackSource()` 暂保留为兼容包装，不再直接维护第二套快照状态。

显式结果载入方法 `loadUnifiedExportResultAsCurrent()` 和 `loadExportResultAsCurrent()` 不取得写文件租约。它们必须先完成 dirty guard，再根据 FileSession 结果处理：

| FileSession 结果 | 播放器行为 |
|---|---|
| `confirmation_required` | 完全不变 |
| `loaded` | 发出 `editorFilePlaybackRequested` |
| `unchanged` | 因用户是显式载入，仍发出 `editorFilePlaybackRequested` |
| `blocked` / `rejected` | 完全不变 |

`FileSessionViewModel.setFileChangeBlocker()` 最终只注册一个合并谓词：

```text
EditSession.anyExporting
OR ProcessingSession.isBusy
OR AudioPlayer.mediaOperationBusy
```

调用顺序必须避免由当前操作先取得播放器租约、再被同一合并 blocker 自锁。

## 9. 播放来源合同

新增独立 `playbackOrigin`，保留现有 `currentPlaybackSourceType` 兼容 ProcessingSession：

| `playbackOrigin` | 文案 | 兼容类型 |
|---|---|---|
| `folder_tree` | 文件夹树载入 | 不要求映射到新兼容键 |
| `transcode_source` | 转码源文件 | 不要求映射到新兼容键 |
| `transcode_output` | 转码输出结果 | 不要求映射到新兼容键 |
| `editor_file` | 编辑文件 | `original` |
| `pitch_preview` | Pitch 试听 | `preview_cache` |
| `editor_export` | 编辑导出结果 | `export_result` |

播放器 UI 的启用状态必须读取 `hasPlaybackSource`，不能继续用代理 FileSession 的 `hasCurrentFile`。

`currentPlaybackSourceType` 只表达 ProcessingSession 兼容类型，`playbackOrigin` 表达用户可见来源；二者不得混为一个字段。未知 origin 必须保留为 `unknown`/明确未知状态，不能静默归类为 `editor_file` 或兼容类型 `original`。

输出设备刷新遵守：

- 当前设备仍存在时不自动切换；
- 当前设备被移除时安全回退到系统默认设备；
- 回退保留现有音量和静音状态，不自动开始播放。

## 10. 自动转码筛选合同

`TaskQueueModel` 继续保存唯一任务快照；过滤代理不复制任务。

| 筛选 | 谓词 |
|---|---|
| 全部 | 全部任务 |
| 等待处理 | `enabled_for_run=true` 且状态为 `QUEUED/READING/WAITING` |
| 处理中 | 状态为 `PROCESSING` |
| 本轮跳过 | `enabled_for_run=false` |
| 已完成 | 状态为 `COMPLETED` |
| 失败 | 状态为 `FAILED` |

`SKIPPED_STATUS` 和 `CANCELLED_STATUS` 暂只在“全部”显示。`excludedCount` 是“本轮跳过”数量，`skippedCount` 不是。`waitingCount` 必须聚合已参与任务的 `QUEUED + READING + WAITING`，不能沿用当前仅统计 `WAITING` 的口径。各筛选独立计算，不要求简单相加等于总数。

过滤变化只能 invalidate proxy，不能额外 reset source model。任务身份继续使用规范化路径；筛选后不可见的选择必须清理。

## 11. 任务播放器与检查器合同

### 播放动作

- 双击任务只请求载入源文件，不播放。
- 源文件必须存在且 Qt 可直接播放。
- `.ncm` 源播放禁用，提示转换后载入结果。
- 正式输出必须是已完成任务、非空正式路径且文件实际存在。
- “打开输出目录”条件不能复用为“可播放正式输出”。
- 转换完成不得发出播放请求。
- AutoConvertViewModel 不直接持有或操纵 QMediaPlayer。

### 检查器

- 初始为自动模式。
- 自动侧栏条件：`width >= 1900 && height >= 1200`。
- 低于阈值时默认隐藏。
- 小尺寸人工打开使用覆盖式 Drawer。
- 用户切换为会话状态，不写配置。
- 详情按当前选择路径从同一任务源查询。
- watcher 快照中的 `source_type` 是输入格式，`source` 才是任务来源（如 `qml_file`、`qml_scan`）；检查器必须分开标注，不能把格式显示成来源类型。

## 12. 歌词时间点合同

- 时间来自 PlayerSession 已确认的真实 position。
- 格式与 Legacy 算法一致：`[mm:ss.xx]`、百分之一秒、累计分钟。
- 示例：201450 ms → `[03:21.45]`；3753450 ms → `[62:33.45]`。
- 有选区使用 `selectionStart` 所在行，无选区使用光标行。
- 多行选择只处理起始行。
- 替换行首第一个合法 LRC 时间戳；没有则插入行首。
- 不换行、不播放、不写文件，只更新 EditSession 歌词草稿。
- 点击工具前保存光标/选区，完成后恢复焦点。
- ±2 秒 seek 在 0 和 duration 边界钳制。
- 当前版本不增加快捷键或配置项。

## 13. 布局与全局组件合同

- 保留 Windows 原生标题栏；Phase 5.9.5 不进入 frameless。
- 二级导航高度 40～48 px。
- 全局播放器标准 96 px；窗口高度 `<800` 使用约 82 px。
- 文件夹 Pane 220/260/360 px，当前 `visible=false`。
- Pane 隐藏后不得留下 SplitView handle 或空白。
- 任务检查器的自动断点是 1900×1200，不是只按宽度。
- 设置和日志打开、关闭均不改变工作区。
- 隐藏 StackLayout 页面不得继续接收 DropArea、快捷键或活动焦点。

## 14. 兼容组件合同

Phase 5.9.5 可停止生产加载，但不删除或改名：

- `SidebarNavigation.qml`
- `RightInspector.qml`
- `PlayerBar.qml`
- `CurrentFileBar.qml`
- `LyricsCoverPage.qml`
- `AnalysisPage.qml`
- `SingleFileConvertPanel.qml`
- `ScanPreviewPanel.qml`
- `PreviewCachePanel.qml`
- `ExportResultPanel.qml`
- `CoverPreviewCard.qml`

测试应迁移语义断言，不以“新结构已上线”为理由删除历史安全测试。

## 15. 测试迁移矩阵

### Phase A：PlayerSession 安全

保留并扩展：

- `tests/test_qml_audio_player.py`
- `tests/test_qml_file_session.py`
- `tests/test_qml_editor_workspace_phase583.py`
- `tests/test_audio_processing_session.py`
- `tests/test_qml_editor_export_phase584.py`
- `tests/test_edit_export_integration.py`
- `tests/test_qml_unified_edit_export_dialog.py`
- `tests/test_processed_audio_export.py`

需要改写的旧断言：

- 显式载入结果必须先 prepare/release 再请求 FileSession；
- reload 编辑文件必然同步播放器；
- 清除编辑文件必然清空任意播放器来源；
- restore 无快照时自动回到当前编辑文件。

其中至少以下现有测试编码了待修正的危险调用顺序，Phase A 不得在未替换其语义前直接删除：

- `tests/test_qml_editor_export_phase584.py::test_unified_export_releases_restores_and_loads_result_only_when_explicit`
- `tests/test_audio_processing_session.py::test_pitch_export_result_stays_separate_until_explicit_load`

新增：

- `tests/test_qml_phase595_player_session_safety.py`

Phase A targeted：

```powershell
python -B -m pytest -q -p no:cacheprovider `
  tests/test_qml_audio_player.py `
  tests/test_qml_file_session.py `
  tests/test_qml_editor_workspace_phase583.py `
  tests/test_audio_processing_session.py `
  tests/test_qml_editor_export_phase584.py `
  tests/test_edit_export_integration.py `
  tests/test_qml_unified_edit_export_dialog.py `
  tests/test_processed_audio_export.py `
  tests/test_qml_phase595_player_session_safety.py
```

### Phase B：持久化外壳与导航

保留并调整：

- `tests/test_qml_sidebar_accessibility.py`
- `tests/test_qml_status_copy.py`
- `tests/test_qml_core_page_layouts.py`
- `tests/test_qml_inspector_and_button_regressions.py`
- `tests/test_qml_native_2k_window_layout.py`
- `tests/test_qml_runtime_modes.py`
- `tests/test_qml_log_drawer_layout.py`

新增：

- `tests/test_qml_phase595_workspace_shell.py`

需要退役的是机械断言，不是整个测试文件：

- 六个同级可见模块；
- 页面必须由单个 Loader 销毁和重建；
- 左侧 Sidebar 固定 218 px；
- 通用 RightInspector 固定占据 292 px；
- 设置必须作为普通模块页切换；
- `analysis` 必须出现在生产导航。

新增测试必须实例化真实 AppShell，验证同一工作区实例身份、状态保留和兼容路由；源码字符串断言只能作为补充。

### Phase C：全局播放器

保留并调整：

- `tests/test_qml_audio_player.py`
- `tests/test_qml_component_states.py`
- `tests/test_qml_core_page_layouts.py`
- `tests/test_qml_light_theme.py`
- `tests/test_qml_native_2k_window_layout.py`
- `tests/test_qml_pitch_shift_workflow.py`

新增：

- `tests/test_qml_phase595_global_player_dock.py`

退役机械断言：

- `PlayerBar` 必须位于 `AudioEditorPage`；
- 没有 FileSession 当前文件时播放器 UI 必须全部禁用。

### Phase D1：音频编辑工作区

保留并调整：

- `tests/test_qml_editor_workspace_phase583.py`
- `tests/test_qml_editor_responsibility_phase593.py`
- `tests/test_qml_core_page_layouts.py`
- `tests/test_qml_unified_edit_export_dialog.py`
- `tests/test_qml_cover_readonly.py`
- `tests/test_qml_lyrics_readonly.py`
- `tests/test_qml_metadata_readonly.py`

新增：

- `tests/test_qml_phase595_editor_workspace.py`

### Phase D2：时间点

保留并扩展：

- `tests/test_qml_audio_player.py`
- `tests/test_edit_session_lyrics.py`
- `tests/test_qml_lyrics_readonly.py`

新增：

- `tests/test_qml_phase595_lyrics_timestamp.py`

必须包含真实动态 QML TextArea 光标/选区测试，不能只做源码字符串断言。

### Phase E：自动转码筛选、播放与检查器

保留并调整：

- `tests/test_qml_phase591_auto_convert_simplification.py`
- `tests/test_qml_phase592_queue_control_center.py`
- `tests/test_qml_auto_convert_list_bridge.py`
- `tests/test_qml_auto_convert_layout.py`
- `tests/test_qml_convert_action_bar_geometry.py`
- `tests/test_qml_inspector_and_button_regressions.py`

新增：

- `tests/test_qml_phase595_task_filters_and_inspector.py`

该文件同时覆盖筛选计数、选择失效、任务源/结果播放器路由和检查器数据语义。任何新增 QML 数组 Slot 必须有 JavaScript Array 经 Qt 元对象进入 Python 的测试。

### Phase F：响应式与完整回归

保留页面级断言并调整外壳假设：

- `tests/test_qml_phase594_workspace_density.py`
- `tests/test_qml_native_2k_window_layout.py`
- `tests/test_qml_light_theme.py`
- `tests/test_qml_log_drawer_layout.py`
- `tests/test_qml_sidebar_accessibility.py`

新增：

- `tests/test_qml_phase595_folder_pane_and_responsive.py`

`test_qml_phase594_workspace_density.py` 当前把 218 px Sidebar 和 292 px Inspector 写入可用视口前提；Phase F 必须迁移为新外壳真实几何，但继续保留各页面内容密度和滚动规则。

## 16. 每阶段共同门禁

1. 本阶段 targeted tests。
2. 默认及受影响旧模块键 offscreen smoke。
3. `tests/test_qml_runtime_modes.py` 和 capability 测试。
4. 独立 smoke 前后 `config.json` SHA256。
5. 完整 `python -B -m pytest -q -p no:cacheprovider`。
6. Legacy import 与 Safe Start。
7. 无新增 QML ReferenceError、binding loop、anchor conflict 或 undefined。
8. 无新增 warning。
9. 无由本阶段产生的 Python/FFmpeg/ncmdump/watcher 残留。
10. 涉及媒体时验证源 SHA、no-clobber 和 Windows 释放/重命名。
11. 阶段结束更新 `Codex_memory` 并向用户汇报，然后停止；不得自动进入下一阶段。

## 17. 冻结范围

Phase 5.9.5 不修改：

- `converter.py` 转换算法；
- watcher 调度、生命周期与转换状态机；
- FFmpeg/NCM/Pitch 算法；
- `EditExportService`、`ProcessedAudioExportService` 的安全发布算法；
- Metadata/Lyrics/Cover 的源文件写入边界；
- no-clobber、源 SHA 和临时副本策略；
- Legacy Widgets UI/播放器；
- capability 默认授权；
- `config.json` 持久化语义；
- WAV/raw AAC 当前不支持边界；
- 文件夹树真实功能；
- 时间点快捷键与未来设置；
- Release 打包。

watcher 只允许在 Phase E 经专项测试后增加检查器所需的只读运行结果字段，不得改变状态机。

## 18. Phase A 精确进入范围

下一阶段生产代码只允许修改：

- `ui_next/bridge/audio_player_viewmodel.py`
- `ui_next/bridge/file_session_viewmodel.py`
- `ui_next/bridge/edit_session.py`
- `ui_next/bridge/audio_processing_session.py`
- `main_qml.py`

此外只允许修改 Phase A 对应测试、本契约与 Phase A 完成后的项目记忆文档。Phase A 不创建或修改任何 QML 文件。

Phase A 不修改 AppShell、导航、任务队列、任务菜单、全局播放器 QML、歌词时间点 UI 或文件夹 Pane。

Phase A 还明确冻结：

- `converter.py`、`watcher.py`、`AutoConvertViewModel`、`TaskQueueModel`；
- capability、运行模式、配置写入和主题语义；
- Legacy Widgets 与旧播放器；
- Metadata/Lyrics/Cover、Pitch、导出和 no-clobber 算法本身；
- FFmpeg/NCM、扫描、转换和缓存算法。

Phase A 开始前必须：

1. 重新计算第 4.1 节文件哈希；
2. 检查现有 `python main_qml.py` 进程；
3. 记录 `config.json` 哈希；
4. 先写失败测试证明当前风险；
5. 完成并汇报 Phase A 后停止。

## 19. Phase 5.9.5-A 完成记录

### 19.1 实际修改范围

生产代码仅修改：

- `ui_next/bridge/audio_player_viewmodel.py`
- `ui_next/bridge/file_session_viewmodel.py`
- `ui_next/bridge/edit_session.py`
- `ui_next/bridge/audio_processing_session.py`
- `main_qml.py`

测试仅修改或新增：

- `tests/test_qml_audio_player.py`
- `tests/test_qml_editor_workspace_phase583.py`
- `tests/test_audio_processing_session.py`
- `tests/test_qml_editor_export_phase584.py`
- `tests/test_qml_phase595_player_session_safety.py`

未修改任何 QML 文件，也未修改 AppShell、导航、任务队列、任务菜单、watcher、converter、capability、运行模式、配置写入、FFmpeg/NCM/Pitch 算法、导出/no-clobber 算法或 Legacy Widgets。

### 19.2 合同落实结果

- `currentFileChanged` 只表示真实编辑文件切换；`currentFileReloaded` 只驱动 reader/Edit/Processing 刷新；`editorFilePlaybackRequested` 独立表达显式播放器同步。
- reload、编辑文件清除和缺失处理不会无条件覆盖或清空无关的文件夹/转码播放源。
- `beginFileOperation(owner)` / `finishFileOperation(token, restore)` 是唯一媒体事务状态；兼容包装复用同一 token lease，不维护第二套快照。
- 媒体事务非重入，租约期间拒绝普通播放源切换；错误、过期、重复 token 均不能结束当前事务；无快照时不回退 FileSession。
- 统一编辑结果与 Pitch 结果载入先通过 dirty guard，不提前 release；`confirmation_required`、`blocked`、`rejected` 和用户取消均保持 PlayerSession 完全不变。
- 正式编辑/Pitch 导出在实际写文件阶段持有 token；正常、失败、取消、过期、worker 启动异常和 shutdown 均按精确 token 收尾。
- `main_qml.py` 只设置一个合并 blocker：`EditSession.anyExporting OR ProcessingSession.isBusy OR AudioPlayer.mediaOperationBusy`。
- PlayerSession 已提供 `hasPlaybackSource`、`currentPlaybackFileName`、`playbackMatchesEditorFile`、`playbackOrigin`、`muted`、`seekStepMs=2000`、前进/后退和 `[mm:ss.xx]` 时间文本；设备回退保留音量/静音且不自动播放。

### 19.3 完成时工作副本 SHA256

| 文件 | SHA256 |
|---|---|
| `main_qml.py` | `985E28291EEC931FF94E7CDEE8137B3195113A86BCAF912890EC70BF969FC879` |
| `ui_next/bridge/audio_player_viewmodel.py` | `09A4A1A80BBCFD77D5EA37BB3CBCF04DF683100AEC3392D0036E505938811CA7` |
| `ui_next/bridge/file_session_viewmodel.py` | `746813460F2E47C26E5950781FB2C8E38C4229EE5097CC8C3CF443F1B635C276` |
| `ui_next/bridge/edit_session.py` | `5BDEB2170F5FF59B81D5949304C302C3DCD82D7257E0AE39E9540599F94AF621` |
| `ui_next/bridge/audio_processing_session.py` | `E50308499A1D39A75913287C00FD27DF51AFAF5EC1798C466B1FA293107D16F0` |
| `tests/test_qml_audio_player.py` | `120AC2AD501DC56D9047CC1A226CEE474B4F440406CD8C022560646D2CCCBABA` |
| `tests/test_qml_editor_workspace_phase583.py` | `45796CE65BFD7D7044C86EE5D79CF2447B507E2A0DEF11ADD2CF87E44BF33B48` |
| `tests/test_audio_processing_session.py` | `334CE6A5FF2A07FFDA8032F988E4E9CE9E983E988057382AC9E2DEB1D3637DEF` |
| `tests/test_qml_editor_export_phase584.py` | `00C0F02C691433858D8C085E385940CDD815B14B3672B83E1D3F35D8A2ECDAD7` |
| `tests/test_qml_phase595_player_session_safety.py` | `DC4350E0CE3ADE9B5272EC53A6F9F8B8E5A83A258FF00378417DA6A968A7A345` |

### 19.4 验证结果

- Phase A 九文件定向回归：`84 passed, 2 subtests passed`。
- 完整回归最终复跑：`483 passed, 2 warnings, 20 subtests passed`。
- 首次完整回归在旧 Widgets 临时 FLAC 清理阶段偶发一次 Windows `WinError 32`；失败单测复跑 `1 passed`，随后完整复跑通过，未修改冻结的 Legacy 媒体代码。
- 默认及 `autoConvert`、`audioEditor`、`metadata`、`lyricsCover`、`analysis`、`settings`、`--qml-open-settings` 八组 offscreen smoke 全部通过。
- Legacy Safe Start、QML runtime modes 与 capability 专项：`30 passed`；Legacy `gui` / `MainWindow` import 通过。
- `git diff --check` 与目标 Python 文件编译检查通过；未增加 warning。
- `config.json` SHA256 仍为 `EA8BE86CDF7FC7C9351B7F961D9D8B9BC97AD3D414FB7B6A8B8376B8E82CA72B`；`config.json.bak` 仍为 `CBED09046D02FC40A229CED3D9BD0E8642F80C13185B1AED3862BB44ED14B1E4`。
- 验证结束后未发现 Python、FFmpeg 或 ncmdump 残留进程。

### 19.5 阶段门禁

Phase A 已按精确文件清单完成提交收尾但未推送。Phase B 未开始，只有在用户明确要求后才能进入。

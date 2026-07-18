# Phase 5.9.3｜文件信息、封面与歌词职责重新划分

## 结论

Phase 5.9.3 已完成。生产 QML 现在按用户任务划分：

- 文件信息页：Metadata 草稿、完整封面草稿操作、文件技术摘要。
- 歌词页：歌词来源、正文预览、`.lrc` 导入、歌词草稿、歌词另存与统一导出入口。

兼容模块键 `lyricsCover`、`LyricsCoverPage.qml` 文件名和既有 objectName 暂时保留，但生产可见名称统一为“歌词”。本阶段没有进入 Phase 5.9.4 的整体布局重构。

## 迁移前后

迁移前：

```text
文件信息页 → Metadata + 文件摘要 + 封面只读预览 + 歌词检测摘要
歌词 / 封面页 → 歌词 + 完整封面草稿编辑
```

迁移后：

```text
文件信息页 → Metadata + 文件摘要 + 完整封面草稿编辑
歌词页     → 歌词来源 + 正文 + 歌词草稿
```

`CoverDraftEditor` 由 `MetadataPage.qml` 加载，提供原始/当前草稿预览、替换、移除、恢复、dirty 与导出支持状态。`LyricsCoverPage.qml` 不再加载封面组件，也不再引用 `coverViewModel`、`coverDirty` 或封面导出结果。

## ViewModel 与会话所有权

- `main_qml.py` 仍只创建一个 `MetadataViewModel`、一个 `LyricsViewModel`、一个 `CoverViewModel` 和一个 `EditSessionViewModel`。
- `FileSessionViewModel` 仍是唯一当前文件、`sessionGeneration` 和异步读取协调者。
- 原 `CoverViewModel` 继续负责封面读取；其 `coverReadApplied` 结果进入同一个 `EditSessionViewModel.loadCoverResult()`。
- Metadata、Cover、Lyrics 的 original/draft/dirty 仍全部由同一个 `EditSessionViewModel` 保存。
- 文件切换仍只使用 `edit_session_view_model.hasUnsavedDrafts` 作为统一 dirty guard。
- 页面切换只修改 `AppStateViewModel.currentModuleKey`，不建立新文件会话、不重新实例化 ViewModel，也不清除草稿。

## 统一导出与安全边界

- `EditExportDialog` 仍是唯一正式音频编辑副本导出窗口。
- 文件信息页的 Metadata 与 Cover 入口、歌词页的 Lyrics 入口均调用 `openUnifiedExportDialog(...)`。
- `EditExportService`、统一输出路径校验、写后验证和 no-clobber 发布逻辑未修改。
- Metadata、Cover、Lyrics 修改只更新内存草稿；源音频和原 `.lrc` 不作为写入目标。
- Preview / smoke 不读取或导出真实媒体；默认启动不自动执行文件操作。
- 自动转码页面、任务队列、watcher、`ConvertThread`、FFmpeg/NCM、播放器、Pitch、设置、主题与大工作区导航层级均未修改。

## 页面命名

以下生产可见文案已统一：

- 左侧导航：“歌词”
- 模块说明：只描述歌词来源、正文、导入与草稿
- 音频编辑快捷入口：“编辑歌词”“查看歌词”
- 文件来源标签：“歌词”
- Right Inspector 用途摘要：“歌词摘要”“封面摘要”

兼容键 `lyricsCover` 不属于用户可见文案，继续用于路由和自动化定位。

## 自动化验证

```powershell
python -m compileall .
python -m pytest -q -p no:cacheprovider
python -B main_qml.py --qml-smoke-test
python -B main_qml.py --qml-smoke-test --qml-open-module=metadata
python -B main_qml.py --qml-smoke-test --qml-open-module=lyricsCover
python -B main_qml.py --qml-smoke-test --qml-open-module=autoConvert
python -B -c "import gui"
python -B -c "from ui.main_window import MainWindow"
```

结果：

- Phase 5.9.3 及编辑专项：`61 passed`。
- 完整 pytest：`451 passed, 2 warnings, 5 subtests passed`。
- 2 条 warning 均为既有 Qt `QMouseEvent` 构造弃用提示。
- QML 默认、文件信息、歌词、自动转码 smoke 均返回 0。
- 默认 QML 与 Legacy Safe Start 均完成 3 秒受控短启动。
- `import gui`、`from ui.main_window import MainWindow` 均返回 0。
- 上述 smoke/短启动前后 `config.json` SHA256 均为
  `CBED09046D02FC40A229CED3D9BD0E8642F80C13185B1AED3862BB44ED14B1E4`。

## 真实媒体验证

单独复跑 MP3 / FLAC / M4A / OGG / OPUS 五种真实媒体的 Metadata + Cover + Lyrics 组合导出与回读，结果 `5 passed`。每个样本均验证：

- 输出副本包含新 Metadata、封面和歌词；
- applied modules 为 Metadata、Cover、Lyrics；
- 源文件 SHA256 前后不变；
- 正式输出使用既有 no-clobber/新路径规则。

## 未完成与后续边界

- 已执行一次可见 QML 页面结构检查：左侧导航显示“文件信息 / 歌词”，文件信息页可见 Metadata 与封面草稿区，歌词页只显示歌词来源、预览和草稿编辑。
- 本轮没有完成文件选择、封面替换/移除/恢复、跨页面草稿保持和文件切换提示的鼠标级完整人工 GUI 场景，仍需按用户验收路径补验。
- `CoverPreviewCard.qml` 作为历史兼容组件保留，但生产页面已不加载；删除前仍需单独确认历史测试引用。
- `LyricsCoverPage.qml`、`lyricsCover` 与兼容 objectName 暂不重命名，避免无收益的引用扩散。
- 文件信息页完整横向布局整理、卡片密度和像素级对齐留给 Phase 5.9.4。
- 本阶段完成后停止，不自行进入 Phase 5.9.4。

# 下一阶段交接

## 当前基线

- 分支：`codex/v5_P1`
- Phase E 提交：`cdd1d5e`，未推送。
- Phase F 空接口与 Phase F2 用户级文件浏览：工程实现、自动化回归和提交收尾均已完成，根据用户授权提交为 `f4445d7`，未推送。
- 顶部一级工作区与全局工具语义优化已提交为 `b22b1e5`，未推送。
- 完整自动化：`553 passed, 2 warnings, 70 subtests passed`。
- `config.json` 内容未被自动化测试改写；文件浏览状态只在默认用户模式的显式交互后持久化。

## 入口与运行

- 默认 QML：`python -B main_qml.py`
- 安全 smoke：`python -B main_qml.py --qml-smoke-test --qml-open-module=autoConvert`
- 安全预览：`python -B main_qml.py --preview`
- Legacy Widgets：`python gui.py`
- Legacy 安全导入：`QONIC_LEGACY_SAFE_START=1 python -c "import gui"`

## 已完成架构

- 一级工作区只有“自动转码 / 音频编辑”，二级导航位于顶部。
- AppShell 持有唯一全局播放器；设置和日志为全局 Overlay/Drawer。
- 自动转码六类筛选投影同一 `TaskQueueModel`，任务源/正式输出播放只改变唯一 PlayerSession。
- 音频编辑使用唯一 CurrentFileBar、FileSession、EditSession 和 ProcessingSession。
- 歌词复制/插入共享 millisecond/centisecond 精度设置，默认千分之一秒。
- 独立唯一 `FolderBrowserModel` 提供真实懒加载树、自动刷新、搜索、收藏、最近目录和状态恢复。
- FolderBrowserPane 使用 `SplitView` 调整宽度并可从 Pane 或顶部收起/展开；跨工作区保持同一实例。
- 人工验收补充已强化选中高亮、后台封面小图、异步 TreeView 深度校验，以及文件树到当前编辑/转码主工作区的拖放。
- 顶栏已按人工验收要求移除运行模式和长功能能力摘要黄色框；底层模式与能力授权未改。

## 文件浏览合同

- 默认用户模式可用；Preview/smoke 不读取真实目录。
- 目录和文件单击只选择，箭头只展开，树刷新不自动入队。
- 普通音频双击只载入全局播放器，固定 `autoplay=false / position=0 / origin=folder_tree`。
- NCM 可显式加入唯一任务队列，但不能直接播放或进入编辑器。
- 普通音频可拖到当前编辑或转码工作区；NCM 只可拖到转码区。释放点不在主工作区时不执行。
- 展开时每个可见 delegate 必须匹配真实模型深度，禁止旧 delegate 以错误层级继续显示；不要以异步载入瞬间的扁平行索引作为可见性条件。
- 右键进入编辑器继续经过 FileSession dirty guard；加入队列来源为 `folder_browser`。
- 当前根、收藏、最近目录、Pane 显示状态和宽度是应用 UI 状态，显式交互后原子写入 `config.json`。

## 仍不可破坏的边界

- 不覆盖、删除或静默改写源音频和原 `.lrc`。
- 正式输出继续使用临时副本和 no-clobber 发布。
- 不创建第二个播放器、TaskQueueModel、FileSession、EditSession 或文件夹模型。
- 不复用 `EditorFileBrowserViewModel` 实现全局文件树。
- 不因选择、展开、搜索或自动刷新而扫描入队、自动播放或自动转换。
- 未经用户另行确认，不扩展到 converter、任务状态机、FFmpeg/NCM/Pitch 算法、导出服务或 Legacy Widgets。

## 当前人工验收

先按 `docs/PHASE_5_9_5_F_FOLDER_PANE_RESPONSIVE_ACCEPTANCE.md` 验证文件浏览，再对 A～F 做完整回归：

- Windows 真实 100% / 125% / 150% DPI；
- 六档窗口、播放器和检查器阈值；
- 自动转码筛选、队列滚动保持、源/结果播放与检查器；
- 文件信息、封面、歌词时间点、Pitch 和统一导出；
- 文件树的选择、展开、自动刷新、搜索、收藏/最近目录、状态恢复及五项右键动作；
- PlayerSession 与 EditorSession 不同源时的来源提示和 dirty guard。

精确提交已经完成。后续继续不使用 `git add .`，不处理 `.reasonix/`、`Code_Review_Packages/` 或 `config.json.bak`；未经用户授权不推送。Windows 真实 DPI、真实媒体鼠标操作和左侧隐藏状态仍按验收文档保留为最终人工门禁。

## 后续方向

Phase 5.9.5-A～F2 工作分区整合已经结束。下一阶段开始前重新冻结范围；若工作必须扩展到转换算法、正式导出安全或其他未提及模块，先暂停并确认。

# UI 重构后全量变更总结

日期：2026-07-14
当前定位：`v5.0 Internal Test / v5.0 内部测试版`

## 结论先行

本项目已从单一 PySide6 Widgets 主界面，演进为 **Legacy Widgets 稳定路径 + QML 工作台迁移路径并存** 的内部测试基线。

- 工程能力：扫描、队列、转换、watcher、设置保存，以及既有播放、元数据、歌词、封面和 Pitch 工作流已经接入并完成受控回归。
- 数据安全：`CapabilityGate`、no-clobber 发布、源文件保护、显式保存确认和 File/Edit/Processing 三类会话边界仍然有效。
- 用户体验：未通过。当前界面仍以能力验证和人工验收步骤组织，不能直接作为普通用户最终工作流。

因此，`v5.0 Internal Test` 只用于内部人工测试与代码审查；后续首先重组用户任务流，不继续向 Phase 5.7 堆叠功能。

## 架构演进

| 阶段 | 主要改动 | 结果 |
| --- | --- | --- |
| Legacy Widgets 收口 | 自动转码、音频编辑、播放器、项目文件夹树、缓存管理、Pitch 滑杆与 Safe Start 整理。 | 旧 `gui.py` 路径保留可运行，启动副作用可用 Safe Start 隔离。 |
| QML 工作台基础 | 新增 `main_qml.py`、`ui_next/qml/`、`ui_next/bridge/`，建立导航、状态栏、右侧检查器、日志抽屉、页面和组件体系。 | 不替换旧界面，迁移路径可独立 smoke。 |
| 安全预览阶段 | 默认 Preview Mode；CapabilityGate 按动作授权；只读/模拟页面先行。 | 默认不扫描、不监听、不转换、不写配置。 |
| 会话与处理边界 | 引入 FileSession、EditSession、ProcessingSession；拆分播放源、编辑草稿、Pitch 试听缓存与导出发布。 | 编辑、试听、导出和加载结果不再混为同一动作。 |
| 视觉与可访问性 | Theme Token、深浅主题、统一按钮/卡片/空状态/状态徽章、轻量动画、响应式布局和焦点语义。 | 不把主题或动画写入配置，也不改变业务授权。 |
| Phase 5.7 真实业务回归 | 目录扫描、显式入队、串行批量转换、NCM、任务控制、watcher 与受限配置保存。 | 功能可用，继续受 capability 和 no-clobber 约束。 |
| User Trial Mode | `QONIC_QML_USER_TEST=1` 注入固定人工验收能力集并显示用户可读状态。 | 仅供验收，不是最终产品模式。 |

## 主要代码结构

| 目录/入口 | 责任 |
| --- | --- |
| `gui.py`、`ui/` | 保留的 Widgets 稳定路径和系统级原生交互。 |
| `main_qml.py` | QML 应用入口、能力注入、ViewModel 组合与 smoke 参数。 |
| `ui_next/qml/` | AppShell、导航、页面、主题与共享组件。 |
| `ui_next/bridge/` | QObject ViewModel、会话、受限服务、no-clobber 发布和业务状态桥接。 |
| `single_file_convert.py` | 单文件转换的独立 no-clobber 服务，不经旧 watcher 队列。 |
| `docs/PHASE_5_7_CLOSEOUT.md` | 本轮工程、安全、人工验收与测试结论。 |

## 功能变化

### 自动转码与队列

- QML 自动转码页由只读监控升级为：目录扫描、候选分类、多选/全量显式入队、重复拒绝和队列参数快照。
- 批量路径支持串行任务、验证/NCM 解码/转换/发布阶段、取消当前任务、完成当前后停止、失败重试、移除、终态清理和输出定位。
- watcher 只能在用户显式点击且同时拥有 `watcher_control` 与 `queue_mutation` 时启动；发现新文件只入队，不自动转换。
- 单文件转换可从扫描候选显式交接；输出必须是不存在的新路径，目标格式必须与文件扩展名匹配。

### 音频编辑与处理

- 音频编辑页实现当前文件栏、播放器、Pitch Shift 卡片、试听缓存状态、导出结果和“加载导出结果”的明确分离。
- FileSession 管理当前文件，EditSession 管理标签/歌词/封面草稿，ProcessingSession 管理 Pitch 请求和预览缓存；Pitch 试听不会自动替换编辑文件。
- Pitch Preview 修复 FFmpeg 管道阻塞问题，增加请求级终结、取消、过期请求隔离、有限超时和缓存命中复用。
- 正式导出仍复用 no-clobber 发布；元数据、歌词和封面写入保持显式动作，不因导入或编辑自动发生。

### 设置、日志与界面系统

- 设置页以 pending 草稿工作；只有 capability 允许且用户点击确认保存时才写入配置，写入使用临时文件、单备份和原子替换。
- 日志模型、状态栏、RightInspector 与 LogDrawer 显示运行状态，保留 QML 页面与 Python/Qt 原生系统能力的边界。
- 深色/浅色主题、统一组件状态、可访问名称、焦点环和轻量动画均为会话内表现层，不修改配置或后台行为。

## Capability 与模式

| 模式 | 真实能力 | 用途 |
| --- | --- | --- |
| Preview Mode（默认） | 无 | UI 审查与安全基线。 |
| 显式 capability | 只开放 `QONIC_QML_CAPS` 中被白名单接受的动作 | 开发/专项回归。 |
| User Trial Mode | 固定启用扫描、单文件/批量转换、队列、手动 watcher、显式配置保存、读取、播放、处理和导出。 | 人工验收。 |
| `QONIC_QML_LIVE=1` | 无额外能力 | 兼容标志，不能绕过 CapabilityGate。 |

User Trial Mode 固定能力为：`metadata_read`、`lyrics_read`、`cover_read`、`scan_preview`、`single_file_convert`、`batch_convert`、`queue_mutation`、`watcher_control`、`config_write`、`audio_playback`、`audio_processing`、`audio_export`。

## 不可破坏的安全边界

- `overwrite_file` 始终拒绝；已有目标文件不会被覆盖。
- 源音频不自动删除、移动或改写；同格式与转码路径均保留源文件。
- 正式音频通过临时结果和 no-clobber 发布流程落位。
- 启动时不会自动扫描、启动 watcher 或开始转换。
- 配置、Metadata、Lyrics、Cover 均不因页面加载或草稿编辑自动写入。
- 不绕过 FileSession、EditSession 或 ProcessingSession；Pitch 结果仅在用户明确“加载导出结果”后切换当前文件。
- 本轮没有为 UI 迁移修改 `converter.py`、`watcher.py`、`metadata.py`、`lyrics.py` 的核心算法语义，也没有改变 Phase 5.5 导出安全模型或 Phase 5.6 Pitch 架构。

## 自动化与人工验收基线

| 项目 | 最新记录 |
| --- | --- |
| 指定 Preview Mode QML smoke | 默认入口及 autoConvert、audioEditor、metadata、lyricsCover 均通过。 |
| QML 专项 | capability、Phase 5.7、播放、编辑导出、Pitch：`35 passed, 3 subtests passed`。 |
| 完整回归 | `374 passed, 1 failed, 2 warnings, 3 subtests passed`。唯一失败为 Legacy 临时 FLAC 清理的 Windows `WinError 32`；失败单测立即重跑 `1 passed`。 |
| 安全检查 | `config.json` SHA-256 前后一致；未发现 Python、FFmpeg、ncmdump 或 watcher 残留。 |

完整回归中的 Windows 临时文件锁属于非确定性环境清理问题，不是业务断言失败。本阶段按冻结要求未修改 Legacy 媒体实现来规避它。

## 当前用户体验问题

1. 用户需要理解 capability、扫描候选、入队和输出路径等内部步骤，才能完成基本转换任务。
2. 单文件转换要求填写完整新输出文件名，并手工保证格式下拉与扩展名一致；安全正确但操作负担高。
3. 页面入口、操作顺序、默认行为和状态反馈尚未围绕“我要转换文件”这类普通任务组织。
4. User Trial Mode 是验证入口，不能替代正式产品体验。

## 下一阶段建议

先审查 `docs/NEXT_PHASE_HANDOFF.md`，围绕“选择文件/文件夹 → 选择目标 → 执行 → 找到结果”定义信息架构、默认值、反馈与错误恢复。不得通过开放覆盖、自动执行、绕过 CapabilityGate 或直接改动冻结后端来快速解决体验问题。

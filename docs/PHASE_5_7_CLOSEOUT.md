# Phase 5.7 结项报告

日期：2026-07-14

阶段：QML 核心业务功能集中回归与人工验收入口

## 阶段目标

在不解除 Preview Mode、CapabilityGate、no-clobber 和源文件保护的前提下，恢复 QML 主界面的扫描、队列、批量转换、watcher 与显式配置保存；新增仅供人工验收的 User Trial Mode。

## 最终结论

| 维度 | 结论 | 说明 |
| --- | --- | --- |
| 工程功能 | 通过 | 按既定流程，扫描、队列、转换、监听、设置保存和既有音频编辑链路可运行。 |
| 数据安全 | 通过 | no-clobber、CapabilityGate、源文件保护、显式配置保存继续有效。 |
| 用户体验 | 未通过 | 当前仍以开发/能力验证步骤组织，普通用户不能自然完成任务。 |
| 阶段状态 | 正式结项 | 不再扩展 Phase 5.7；下一阶段应先重组用户任务流程。 |

## 已完成功能

- 后台目录扫描、扫描结果分类、多选/全量显式入队、队列参数快照。
- 单任务串行批量转换、NCM 解码、阶段状态、取消、当前后停止、重试、移除、终态清理和输出定位。
- watcher 显式启动/停止、稳定文件自动入队、输出/临时目录排除；不会启动时静默运行。
- 设置草稿与显式确认保存；配置使用临时文件、单个备份和原子替换。
- `QONIC_QML_USER_TEST=1` 固定人工验收能力集；它不是最终产品模式。

## 自动化与启动验证

| 项目 | 结果 |
| --- | --- |
| `python -B main_qml.py --qml-smoke-test` | 通过 |
| `autoConvert` / `audioEditor` / `metadata` / `lyricsCover` smoke | 4/4 通过 |
| Capability、Phase 5.7、播放、编辑导出、Pitch 专项 | 35 passed，3 subtests passed |
| `python -B -m pytest -q -p no:cacheprovider` | 374 passed，1 个 WinError 32 临时文件清理失败，2 warnings，3 subtests passed |
| 失败单测重跑 | `test_extended_metadata_fields_enter_pending_metadata` 通过（1 passed） |
| 配置安全 | `config.json` SHA-256 前后一致 |
| 残留子进程 | 未发现 Python、FFmpeg、ncmdump 或 watcher 残留 |

完整回归的唯一失败发生在 Legacy 音频编辑测试退出时清理系统临时 `sample.flac`，不是业务断言失败；单测重跑通过。本阶段冻结 Legacy 代码，不针对此非确定性 Windows 锁修改实现。

## 安全边界确认

- 默认 Preview Mode 仍无真实能力。
- User Trial Mode 不能启用 `overwrite_file`；源文件不会自动修改或删除。
- `QONIC_QML_LIVE=1` 不能绕过 CapabilityGate。
- 正式输出仍以临时文件和 no-clobber 发布，不覆盖已有目标。
- watcher、扫描和转换不会在启动时自动开始。
- Metadata、Lyrics、Cover 草稿不会自动写入；Pitch Shift 不会自动替换 FileSession。
- 配置只在用户明确保存并确认后写入。

## 冻结功能矩阵

状态标记：**真实**=已真实接入；**自动**=已有自动化覆盖；**人工**=已通过本阶段基础验证；**体验待重构**=功能存在但不是自然用户流程；**开发模式**=仅供验收/开发；**延期**=Phase 5.8 或后续；**范围外**=不属于本阶段回归。

| 功能 | 冻结状态 | 结论 |
| --- | --- | --- |
| 目录扫描、文件列表 | 真实 / 自动 / 人工 / 体验待重构 | 可用，但入口与结果交接偏测试流程。 |
| 单文件转换 | 真实 / 自动 / 人工 / 体验待重构 | no-clobber 正确；需手工指定完整新文件路径，非最终体验。 |
| 批量转换、任务队列 | 真实 / 自动 / 人工 / 体验待重构 | 串行执行、状态、取消、重试可用。 |
| NCM 解码 | 真实 / 自动 / 人工 | 复用受控临时目录解码链路。 |
| 输出目录、目标格式 | 真实 / 自动 / 人工 / 体验待重构 | 设置草稿与任务快照安全，但配置步骤偏开发化。 |
| watcher | 真实 / 自动 / 人工 / 体验待重构 | 只允许用户显式启动，发现文件只自动入队。 |
| 配置保存、日志 | 真实 / 自动 / 人工 / 体验待重构 | 保存需确认；日志仍偏诊断用途。 |
| 音频播放 | 真实 / 自动 / 人工 | 保持既有安全接入。 |
| Metadata、Lyrics、Cover 编辑 | 真实 / 自动 / 人工 / 体验待重构 | 编辑、草稿与导出边界明确，未自动写回。 |
| Pitch Shift 试听与导出 | 真实 / 自动 / 人工 | 保持 5.6 的 ProcessingSession/no-clobber 模型。 |
| FileSession、EditSession、ProcessingSession | 真实 / 自动 | 会话边界冻结，不允许绕过。 |
| User Trial Mode | 开发模式 / 自动 | 仅为人工验收固定能力集，不是产品体验。 |
| Preview Mode | 开发模式 / 自动 | 默认安全基线，继续保留。 |
| FFmpeg 百分比/ETA、拖入入队、缓存/分析、日志治理 | 延期 | 归入 Phase 5.8 以后，不在本阶段补做。 |
| 覆盖已有文件、删除源文件、暂停伪装 | 范围外 | 继续禁止。 |

## 人工验收结论与用户体验问题

基础人工验证确认功能能按既定步骤运行，未发现新的数据安全阻塞。但用户体验未通过：

1. 页面入口、操作顺序与状态反馈围绕 capability/验收步骤，而非“我要转换一批文件”等用户任务。
2. 单文件转换要求填写完整目标文件路径，且格式下拉与输出后缀必须手工保持一致；安全正确但不自然。
3. User Trial Mode 只是受控测试入口，不能替代最终产品默认流程。
4. 下一阶段应先定义普通用户任务流、默认值、页面入口和反馈层级，不能继续累加底层按钮或快捷入口。

## 临时文件、缓存与 Git

- 本轮完整回归未启用 pytest cache provider；既有 `.pytest_cache/` 未在本轮更新。
- 回归产生了受 Git 忽略的 `Temp/Editor/` 工作区、备份和试听缓存文件；失败单测曾保留一个 `%LOCALAPPDATA%\Temp\...` 系统临时目录，未在该轮删除。
- 未发现残留 Python、FFmpeg、ncmdump 或 watcher 进程。
- 工作区存在大量历史阶段的已暂存、未暂存和未跟踪内容。本次只暂存结项文档及必要项目记忆更新；不创建 commit。

## 下一步

新对话先读取 [NEXT_PHASE_HANDOFF.md](NEXT_PHASE_HANDOFF.md)，从用户任务和交互信息架构开始规划下一阶段；不要直接继续 Phase 5.7 的功能堆叠。

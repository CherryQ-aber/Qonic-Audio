# 下一阶段交接

## 入口与运行

- QML：`python -B main_qml.py`
- QML smoke：`QT_QPA_PLATFORM=offscreen python -B main_qml.py --qml-smoke-test --qml-open-module=autoConvert`
- 人工验收：`python -B main_qml.py`（默认用户模式，无需环境变量）
- 安全预览：`python -B main_qml.py --preview`
- Legacy Widgets：`python gui.py`；安全导入：`CHERRYQ_LEGACY_SAFE_START=1 python -c "import gui"`

## 当前架构与完成阶段

QML → ViewModel → 受限 Service → Legacy backend/FFmpeg/ncmdump。`main_qml.py` 与 `gui.py` 并存。

Phase 5.9.2 已完成任务队列控制中心：Phase 5.9.1 的五种文件入口和单一 watcher 队列保持不变；任务级参与策略、目标格式覆盖、临时输出目录、单文件/选中/全部转换和稳定路径右键选择均复用既有 `ConvertThread`。Phase 5.8.4 的编辑导出与 Pitch 链路继续冻结。

## 运行模式与安全边界

默认 QML 启动为默认用户模式，开放现有非破坏性扫描、统一入队、队列单任务/批量转换、手动 watcher、设置显式保存、播放、处理和导出能力；启动阶段仍不扫描、监听、转换、保存或写文件。

`--preview` 与 `--qml-smoke-test` 均为零真实能力安全入口；后者自动退出并优先覆盖旧环境变量。`CHERRYQ_QML_USER_TEST=1` 仅保留为映射到默认用户模式的兼容入口；`CHERRYQ_QML_CAPS` 保留窄范围专项测试用途；`CHERRYQ_QML_LIVE=1` 不单独授予能力。

## 不可破坏的安全约束

- `overwrite_file` 永远拒绝；不删除或静默改写源音频。
- 正式输出必须走临时文件 + no-clobber 发布。
- watcher、扫描、转换不得启动时自动运行。
- 配置仅在用户明确保存/确认时写入。
- 不绕过 FileSession、EditSession、ProcessingSession；Pitch 结果不自动替换当前文件。
- 元数据、歌词、封面编辑与写入必须显式分离。

## 当前人工验收与下一阶段边界

Phase 5.9.2 的自动化与真实三任务工程验收已通过；下一步先按 `docs/PHASE_5_9_2_TASK_QUEUE_CONTROL_CENTER.md` 人工检查参与/跳过、单文件格式、任务级目录、多选和右键位置操作。

不要自动进入 Phase 5.9.3。只有用户明确启动后才继续；覆盖策略、单文件编码参数、文件夹树和页面密度重排仍不属于当前阶段。

## 明确禁止事项

不开放覆盖、不删除源文件、不修改 Legacy 后端/转换算法/Pitch 架构以快速改善体验；不为修复 Windows 临时锁而修改冻结 Legacy 代码。

## 首先审查

`docs/PHASE_5_9_2_TASK_QUEUE_CONTROL_CENTER.md`、`watcher.py` 的任务策略 getter/setter、`ui_next/qml/components/TaskQueueView.qml`、`ui_next/qml/components/TaskRowDelegate.qml`、`ui_next/bridge/auto_convert_viewmodel.py`、`ui_next/bridge/task_queue_model.py`。

## 当前测试基线

默认用户模式受控启动、QML smoke、Legacy imports、真实三 WAV 任务策略、no-clobber、源 SHA256 和配置哈希守卫均通过。`python -B -m pytest -q -p no:cacheprovider` 最近结果为 **446 passed，2 warnings，5 subtests passed**；warning 仍是既有 Qt `QMouseEvent` 构造弃用提示。

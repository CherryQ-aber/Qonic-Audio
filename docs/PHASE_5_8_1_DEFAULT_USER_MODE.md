# Phase 5.8.1：默认用户运行模式与能力统一

日期：2026-07-15

## 本轮结论

QML 新入口现在以默认用户模式启动：直接运行 `python main_qml.py` 即可使用已经接入的非破坏性工作流，不再要求设置 `QONIC_QML_USER_TEST=1`。`--preview` 和 `--qml-smoke-test` 会显式进入安全预览；smoke 优先级最高，即使进程带有旧环境变量也不会开放真实能力。

## 修改前审查结论

- `main_qml.py` 以前直接调用 `CapabilityGate.from_environment()`；空环境返回空能力，因此无参数启动进入 Preview Mode。
- `QONIC_QML_USER_TEST=1` 才会注入扫描、队列、转换、设置、播放与处理能力，普通启动无法完成已实现工作流。
- ViewModel 构造阶段只创建读取/刷新计时器和页面草稿；不启动 watcher、扫描、转换、FFmpeg、ncmdump 或配置保存。
- 现有 `EditSession`、`EditExportService` 和 `ProcessingSession` 已具备草稿、另存新文件、no-clobber 和不替换原文件的安全路径，无需重写后端。

## 运行模式

| 入口 | 模式 | 能力与副作用 |
| --- | --- | --- |
| `python main_qml.py` | 默认用户模式 | 开放已实现的非破坏性功能；启动本身不扫描、监听、转换、保存或写文件。 |
| `python main_qml.py --preview` | 预览模式 | 零真实能力；用于安全审查。 |
| `python main_qml.py --qml-smoke-test` | 测试模式 | 零真实能力并自动退出；优先覆盖旧环境变量。 |

`QONIC_QML_USER_TEST=1` 现映射到默认用户模式；`QONIC_QML_CAPS` 保留为窄范围兼容启动入口；`QONIC_QML_LIVE=1` 不单独授予能力。旧 `CHERRYQ_*` 名称仅保留迁移期兼容。

## 默认用户能力与永久禁区

- 已开放：文件/Metadata/Lyrics/Cover 读取，扫描、入队、批量与单文件转换、队列维护、手动 watcher、显式配置保存、播放、Pitch 试听/导出、Metadata/Lyrics/Cover 草稿及导出副本。
- 仍禁止：`overwrite_file`、缓存清理、覆盖源文件、删除/移动源文件、静默写回音频或 `.lrc`、启动时自动扫描/监听/转换/保存、Pitch 完成后自动替换当前编辑文件。
- 标签、歌词和封面相关写入能力仅由既有 `EditExportService` 用于用户选择的全新输出路径；服务仍在创建临时副本前校验、并拒绝同源路径和已有输出。

## 验证

- `python -m compileall .`：通过。
- `python -B main_qml.py --qml-smoke-test`：通过，测试模式、零能力。
- `python -B main_qml.py --preview --qml-smoke-test`：通过，预览模式、零能力。
- 受控启动 `python -B main_qml.py` 与 `python -B main_qml.py --preview`：均成功启动并报告预期模式；启动前后 `config.json` SHA-256 不变。
- `python -m pytest -q -p no:cacheprovider`：`384 passed, 2 warnings, 3 subtests passed`。

两条 warning 均为既有 Qt `QMouseEvent` 构造弃用提醒，不影响本阶段断言。

## 转换控制后续修正

- 已修复 `AutoConvertPage.qml` 向 `ConvertActionBar` 与 `TaskQueueView` 传递同名 ViewModel 时的 QML 自引用。此前子组件会得到空对象，尽管默认用户模式已授予转换能力，“开始监听”和“开始转换”仍会错误置灰。
- 页面现先使用 `root.autoConvertBridge` 等别名再传入子组件；默认用户模式下“开始监听”“刷新任务队列”“开始转换”均可点击。是否存在等待任务、是否正在转换等运行时条件仍按原逻辑控制对应按钮。
- 增加真实 QML 页面回归测试，验证能力闸门、ViewModel 与转换控制之间的绑定；未修改 watcher、converter、输出 no-clobber 或源文件保护策略。
- 修复队列读取验证线程的空闲状态误判：`QueuePrepareThread` 以 `keep_running=True` 持续等待新任务；现在仅实际存在“已入队/读取中”准备条目时才显示“读取验证中”并禁用“开始转换”。任务进入“等待处理”后，空闲 worker 不再阻塞用户手动转换。
- 增加 idle prepare worker 下真实 QML Action Bar 可转换断言，以及真实 WAV 入队、完成读取验证后 `hasBackgroundTask=False` 的工作流回归。
- 后续验证：`python -m compileall -q .` 通过；相关测试 `25 passed`；完整回归重跑为 `386 passed, 2 warnings, 3 subtests passed`；`--qml-smoke-test --qml-open-module=autoConvert` 前后 `config.json` SHA-256 不变。

## 范围边界

未修改 `gui.py`、Legacy Widgets、`watcher.py`、`converter.py`、metadata/lyrics/Pitch 的处理核心、输出 no-clobber 策略、NCM 临时目录策略或页面布局。本轮到此结束，不进入 Phase 5.8.2。

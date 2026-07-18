# Phase 5.9.2｜任务队列成为转码控制中心

## 结论

Phase 5.9.2 已将自动转码任务队列扩展为文件级控制中心，同时保留 Phase 5.9.1 的单一队列和统一文件入口。任务可在队列中控制本轮参与、目标格式覆盖、临时输出目录、单文件转换、选中任务转换、失败重试、移除和位置打开。

本轮没有建立第二套任务列表、转换服务或生命周期状态，也没有修改 `convert_audio()`、FFmpeg 参数、NCM、歌词、safe publish、no-clobber、源文件保护、音频编辑区或全局导航。

## 任务策略字段

每个 watcher 任务增加或确认三个内存字段：

- `enabled_for_run`：默认 `true`。`false` 仅表示本轮批量跳过，不改变 `status`，不复用 `SKIPPED_STATUS`。
- `target_format_override`：空值表示跟随本轮调度的全局目标格式；具体值来自 `formats.py` 的统一格式注册表。
- `output_directory_override`：空值表示跟随默认输出目录；具体值为规范化绝对目录，只保存在当前任务中，不写入 `config.json`。

旧任务快照仍兼容原 `target_format` / `output_directory` 字段；新 QML 入队任务显式携带空 override，避免把全局值误判为单文件覆盖。

## 权限与状态

- 等待、失败、取消等非运行任务可以修改参与策略。
- 读取、处理和已完成任务不能修改参与、格式或输出目录策略。
- “本轮跳过”不会删除任务、清空运行数据或改变生命周期状态。
- 重试失败任务会保留三个任务级策略字段。
- 转换线程通过 watcher 的原子领取接口同时检查等待状态和参与策略，防止重复启动或策略变化后的竞态。

## 调度方式

所有转换继续使用 `ConvertThread`，并由稳定的规范化路径过滤：

- `开始转换`：`状态允许转换 + enabled_for_run == true` 的全部任务。
- `转换选中文件`：当前路径选择集合中已启用且可转换的任务。
- `转换此文件`：右键所在任务的一次性显式调度；允许该任务处于“本轮跳过”，但不会永久修改 `enabled_for_run`。
- `转换到……`：为选中任务写入任务级输出目录覆盖，再调用同一个选中任务调度。

转换前使用原子 `claim_pending_file_for_conversion()` 把任务从等待切换为处理，状态结果仍回写同一 watcher 模型。

## 参数解析顺序

目标格式：

```text
target_format_override
→ ConvertThread 本轮默认目标格式
```

输出根目录：

```text
output_directory_override
→ ConvertThread 本轮调度目录
→ 全局默认输出目录
```

QML、Delegate 和 ViewModel 都不拼接最终文件名。最终路径、格式子目录、临时文件、safe publish 与 no-clobber 继续由原转换链路负责。

## 选择与右键

`TaskQueueView` 在 QML 层保存规范化路径数组，不保存或向 watcher 写入行号：

- 单击单选；
- `Ctrl` 切换多选；
- `Shift` 以当前模型的 `pathAt(row)` 建立连续选择；
- 右键未选中行会先把选择收敛到该任务；
- 模型 reset 后通过 `containsPath()` 删除已失效路径；
- 删除任务后不会保留指向旧行号的操作目标。

右键菜单提供本阶段要求的转换、参与、统一格式列表、输出目录、重试、移除和打开位置操作；队列行只保留一个参与复选框，没有堆叠行内按钮。

## Preview 与配置安全

- Preview / smoke 没有 `QUEUE_MUTATION` 或 `BATCH_CONVERT` 能力，不能修改三个任务策略，也不能启动转换。
- 任务级输出目录 setter 不调用 `save_config()`。
- “转换到……”只调用原生目录选择器、任务级 setter 和统一 `ConvertThread`。
- watcher 不会因策略变化自动转换，启动时也不会自动转换。

## 自动化验证

新增 `tests/test_qml_phase592_queue_control_center.py`，覆盖：

- 默认参与、跳过、重新启用和状态机独立；
- 处理中策略修改拒绝；
- 格式/目录覆盖与失败重试保留；
- 中文、空格和长目录；
- 全部转换过滤禁用任务；
- 单文件显式转换禁用任务但不影响其他等待任务；
- 多任务批量策略不写配置；
- Preview 策略与调度 no-op；
- QML 选择使用稳定路径、格式菜单来自统一注册表。

最终自动化结果：

```text
python -m compileall .                                      通过
python -B main_qml.py --qml-smoke-test                     通过
python -B -m pytest -q -p no:cacheprovider                 446 passed, 2 warnings, 5 subtests passed
python -B -c "import gui"                                  通过
python -B -c "from ui.main_window import MainWindow"       通过
默认用户模式受控启动                                         通过，config SHA256 不变
```

2 条 warning 为既有 Qt `QMouseEvent` 构造弃用提示。

真实三任务样本验证：

```text
第一首：启用 + MP3 覆盖 + 默认目录
第二首：本轮跳过
第三首：启用 + 跟随 FLAC + 任务级自定义目录
```

结果为第一、第三首完成，第二首保持等待；已有 `第一首.mp3` 保持原内容，新输出发布为 `第一首 (1).mp3`。三个源文件 SHA256 不变，无正式半成品，`config.json` SHA256 前后一致。

另以 C 盘中文空格 WAV 源文件和 D 盘任务级目录完成真实跨盘 WAV → FLAC；输出位于 D 盘指定目录，源 SHA256 不变，测试目录在验证后自动清理。

## 未进入的范围

- 未进入 Phase 5.9.3。
- 未修改自动转码入口与目录扫描流程。
- 未实现文件夹树或第二套列表。
- 未修改 Metadata、歌词、封面、Pitch、播放器、EditorSession、设置页或大工作区导航。
- 未修改转换核心算法和输出发布策略。

# Phase 5.9.1｜自动转码页面入口简化

## 结论

自动转码生产页面已收敛为单一流程：

```text
添加文件 / 拖入文件 / 扫描目录 / 拖入目录 / watcher
→ watcher 统一任务队列
→ 后台读取与验证
→ 用户手动开始全部转换或右键转换此文件
```

本阶段没有修改转换算法、FFmpeg 参数、NCM 解码、支持格式、no-clobber
发布、Metadata、歌词、封面、Pitch、播放器、文件会话、设置页或音频编辑工作区。

## 页面结构

- `AutoConvertPage.qml` 不再加载 `SingleFileConvertPanel.qml`。
- `AutoConvertPage.qml` 不再加载 `ScanPreviewPanel.qml`。
- `main_qml.py` 不再实例化或注入 `SingleFileConvertViewModel` /
  `ScanPreviewViewModel`。
- 旧组件和旧 ViewModel 文件暂时保留为历史兼容代码，但生产 QML 路径不可达。
- 页面只显示一个 `TaskQueueView`；目录扫描只显示 `ScanSummaryBar`。

## 五种入口

| 入口 | 统一路径 | 队列来源标记 |
| --- | --- | --- |
| 选择文件 | `choose_input_files → enqueue_files → watcher.handle_detected_file` | `qml_file` |
| 拖入文件 | `enqueue_dropped_items → watcher.handle_detected_file` | `qml_drop` |
| 选择目录 | `choose_scan_folder → DirectoryScanThread → watcher.handle_detected_file` | `qml_scan` |
| 拖入目录 | `enqueue_dropped_items → scan_folders → DirectoryScanThread` | `qml_scan` |
| watcher | 既有 `MyHandler.on_created → watcher.handle_detected_file` | `watcher` |

所有入口复用 `formats.is_supported_input_file()` 和 watcher 去重规则。QML
不判断扩展名、不直接修改列表；`.lrc/.LRC` 不会成为音频任务。入队只启动
后台读取/验证，不自动启动转换。

## 单文件右键转换

任务行右键菜单本阶段只增加“转换此文件”。入口调用
`AutoConvertViewModel.start_convert_item(path)`，验证任务为“等待处理”、没有
其他转换线程运行且输出目录有效后，将单一路径交给原有 `ConvertThread`。

`ConvertThread` 仍调用现有 `converter.convert_audio()`，并保持：

- `safe_publish=True`；
- `preserve_source=True`；
- 任务自己的目标格式与输出参数快照；
- 状态回写 watcher 统一任务对象；
- 完成后复用既有输出定位能力。

没有建立第二套转换服务或任务状态机。

## 扫描摘要

目录枚举在 `DirectoryScanThread` 中调用既有 `scan_directory_preview()`，结果
直接在后台交给 watcher 队列。页面只保留以下摘要：

- 扫描文件总数；
- 新增任务数；
- 重复跳过数；
- 不支持格式数（包含 `.lrc/.LRC` 等非音频文件）；
- 扫描中 / 已完成 / 已取消 / 扫描失败。

取消扫描后不再枚举后续文件；扫描服务已经返回并成功入队的任务保留。
页面不保存或显示第二套候选列表。

## 自动化与人工验收

自动化专项位于：

- `tests/test_qml_phase591_auto_convert_simplification.py`
- `tests/test_qml_auto_convert_layout.py`
- `tests/test_qml_convert_action_bar_geometry.py`

最终工程验证：

- 自动转码相关专项：`84 passed`；
- 完整回归：`439 passed, 2 warnings, 5 subtests passed`；
- QML smoke、默认用户模式受控启动、Legacy `gui` / `MainWindow` import 通过；
- 默认启动和 smoke 前后 `config.json` SHA256 不变；
- 真实 WAV 右键单任务转 FLAC 通过，已有同名 FLAC 未覆盖，新输出自动使用
  ` (1)` 名称，源 WAV SHA256 不变；
- 完整回归曾一次出现既有 Legacy 临时 FLAC `WinError 32`，失败用例立即
  单独复跑通过，随后完整复跑全部通过；未修改冻结 Legacy 媒体逻辑。

人工验收：

1. 启动 `python -B main_qml.py`。
2. 确认旧单文件卡片和目录候选卡片消失。
3. 分别选择文件、拖入文件、选择目录、拖入目录，确认都进入同一任务队列。
4. 放入 `.LRC`、图片和文本，确认不产生任务，扫描摘要计入不支持格式。
5. 右键一个“等待处理”任务并选择“转换此文件”，确认其他等待任务不启动。
6. 再用全局“开始转换”处理剩余任务。
7. 手动启动 watcher，放入新音频，确认只入队、不自动转换；停止 watcher。
8. 复查源文件哈希、已有同名输出和新输出名称。

## 后续边界

Phase 5.9.2 才规划完整任务队列右键菜单。本阶段没有新增单任务输出目录、
覆盖策略、编码参数、是否输出开关，也没有实现文件夹树。

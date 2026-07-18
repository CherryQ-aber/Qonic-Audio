# CherryQ Audio Converter v5.0 Internal Test Release Notes

## 版本定位

`v5.0 Internal Test / v5.0 内部测试版` 是 UI 重构后的内部人工测试与代码审查基线，不是正式对外发行版，也不代表最终产品体验已通过。

本版本用于确认 QML 工作台在受控安全边界内能够完成扫描、队列、转换、watcher、设置保存，以及既有音频编辑和 Pitch 工作流；下一阶段将先从普通用户任务流重组交互。

## 本轮范围

- QML 工作台与旧 Widgets 界面并存，入口分别为 `main_qml.py` 和 `gui.py`。
- 默认 QML 进入正常运行，开放已接入的非破坏性扫描、队列、单文件/批量转换、手动 watcher、显式配置保存、读取、播放、音频处理与导出；启动本身不执行这些操作。
- `--preview` 与 `--qml-smoke-test` 保持零真实能力安全入口；`CHERRYQ_QML_USER_TEST=1` 保留为默认用户模式兼容入口，`CHERRYQ_QML_LIVE=1` 不单独授予能力。
- 转换正式输出继续使用临时文件加 no-clobber 发布；不覆盖已有目标，不自动修改或删除源音频。
- FileSession、EditSession、ProcessingSession 继续作为文件、编辑草稿和音频处理状态的边界。

## 验收结论

| 维度 | 结论 |
| --- | --- |
| 工程功能 | 通过：既定流程中的扫描、队列、转换、监听、保存与音频编辑可运行。 |
| 数据安全 | 通过：CapabilityGate、no-clobber、源文件保护、显式确认保存保持有效。 |
| 用户体验 | 未通过：当前路径仍偏开发与能力验证，不能作为最终普通用户体验。 |

详细功能与测试结果见 `docs/PHASE_5_7_CLOSEOUT.md`；UI 重构全量总结见 `docs/UI_REFACTOR_CHANGE_SUMMARY.md`。

## 未包含的承诺

- 不开放覆盖已有文件或删除源文件。
- 不在启动时自动扫描、监听或转换。
- 不把 Metadata、Lyrics、Cover 草稿自动写回。
- 不将 User Trial Mode 作为正式产品模式。
- 不以本内部测试版替代干净 Windows 异机测试、许可证闭合、安装器、签名或正式发布验证。

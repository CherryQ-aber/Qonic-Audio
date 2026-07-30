# Qonic Audio v5.0 Internal Test Release Notes

## 版本定位

`v5.0 Internal Test / v5.0 内部测试版` 是 UI 重构后的内部人工测试与代码审查基线，不是正式对外发行版，也不代表最终产品体验已通过。

本版本用于确认 QML 工作台在受控安全边界内完成扫描、队列、转换、watcher、设置保存、全局播放、统一编辑草稿/导出和 Pitch 工作流。Phase 5.9.5 的用户任务流与工作区整合已经完成工程实现，当前进入发行构建、人工验收和合规收尾。

项目已确认采用开源路线，自有代码以 `GPL-3.0-or-later` 发布。FFmpeg Audio Runtime、ncmdump、PySide6 / Qt 的 B5 对应材料已归档；当前主分发工件确定为 `.7z` 便携包和 SHA-256 清单。安装器、数字签名、自动更新及文件关联留到 RC 之后规划。

## 本轮范围

- 源码保留 QML 工作台与旧 Widgets 兼容入口；v5.0 PyInstaller 发行规范只使用 `main_qml.py`，并显式携带自有 QML 与应用图标资源。
- 默认 QML 进入正常运行，开放已接入的非破坏性扫描、队列、单文件/批量转换、手动 watcher、显式配置保存、读取、播放、音频处理与导出；启动本身不执行这些操作。
- `--preview` 与 `--qml-smoke-test` 保持零真实能力安全入口；`QONIC_QML_USER_TEST=1` 保留为默认用户模式兼容入口，`QONIC_QML_LIVE=1` 不单独授予能力。
- 旧 `CHERRYQ_*` 环境变量在品牌迁移期继续作为兼容别名，但新脚本应统一使用 `QONIC_*`。
- 转换正式输出继续使用临时文件加 no-clobber 发布；不覆盖已有目标，不自动修改或删除源音频。
- FileSession、EditSession、ProcessingSession 继续作为文件、编辑草稿和音频处理状态的边界。

## 验收结论

| 维度 | 结论 |
| --- | --- |
| 工程功能 | 通过：完整自动化回归、四套主题源码 smoke、QML onedir 构建和打包后 smoke 已通过。 |
| 数据安全 | 通过：CapabilityGate、no-clobber、源文件保护、显式确认保存保持有效。 |
| 用户体验 | 待人工发行验收：工作区任务流已完成整合，但真实媒体、DPI、双屏、窗口/托盘和最终视觉尚未全部签字。 |
| 发行策略 | 已确定：GPL-3.0-or-later 开源、`.7z` 主分发；安装器和数字签名延期。带封面音频流修复后需重建下一份候选工件。 |
| RC 状态 | 未晋级：须先通过真实桌面、真实媒体、干净 Windows、第三方合规和品牌图标门禁。 |

详细工作区合同见 `docs/PHASE_5_9_5_WORKSPACE_INTEGRATION_CONTRACT.md`；UI 重构全量总结见 `docs/UI_REFACTOR_CHANGE_SUMMARY.md`。

RC1 的统一版本迁移和工件要求见 `docs/RELEASE_STRATEGY.md`。门禁完成前，版本源、包名和 Windows 版本资源继续保持 Internal Test。

## 未包含的承诺

- 不开放覆盖已有文件或删除源文件。
- 不在启动时自动扫描、监听或转换。
- 不把 Metadata、Lyrics、Cover 草稿自动写回。
- 不将兼容环境变量或测试模式作为正式产品模式。
- 不以本内部测试版替代干净 Windows 异机测试、第三方许可证闭合或正式发布验证。
- 不把可选 7z SFX 视为安装器；当前 GitHub Release 主下载只规划 `.7z`。

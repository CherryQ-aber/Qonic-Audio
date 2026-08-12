# Qonic Audio 5.0.0-beta.1 — Internal Beta Release Notes

## 版本定位

**Internal Beta Build**

This build is part of an ongoing personal software project. It is primarily maintained for personal use and limited testing. It is not an official stable public release.

本构建主要供开发者本人长期使用及有限测试，不代表 Stable、Official 或 Production Release。

本版本用于确认 QML 工作台在受控安全边界内完成扫描、队列、转换、watcher、设置保存、全局播放、统一编辑草稿/导出和 Pitch 工作流。Phase 5.9.5 的用户任务流与工作区整合已经完成工程实现，当前进入发行构建、人工验收和合规收尾。

项目自有代码以 `GPL-3.0-or-later` 发布。FFmpeg Audio Runtime、ncmdump、PySide6 / Qt 的对应材料已随 2026-07-30 权威工件归档；安装器为当前工程能力，便携 `.7z` 可作为受控测试工件。数字签名、自动更新及文件关联是可选增强。

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
| 工程功能 | 历史基线已通过；`5.0.0-beta.1` 候选必须以本轮真实验证结果为准。 |
| 数据安全 | CapabilityGate、no-clobber、源文件保护和显式确认保存保持不变；新 installed-data 路径需验证。 |
| 用户体验 | Internal Beta 候选仍需真实安装、媒体、DPI、双屏、窗口/托盘验收。 |
| 发行策略 | Personal Software Project / Internal Beta；GitHub 仅允许 Pre-release。 |
| Stable 状态 | 当前不存在；Public Stable Gate 已延后，不阻塞 Internal Beta。 |

详细工作区合同见 `docs/PHASE_5_9_5_WORKSPACE_INTEGRATION_CONTRACT.md`；UI 重构全量总结见 `docs/UI_REFACTOR_CHANGE_SUMMARY.md`。

当前 Internal Beta Gate 与未来延后的 Public Stable Gate 见 `docs/RELEASE_STRATEGY.md` 和 `TEST_CHECKLIST.md`。版本号达到 1.x 或更高也不会自动变成 Stable。

## 未包含的承诺

- 不开放覆盖已有文件或删除源文件。
- 不在启动时自动扫描、监听或转换。
- 不把 Metadata、Lyrics、Cover 草稿自动写回。
- 不将兼容环境变量或测试模式作为正式产品模式。
- 不以历史内部测试结果替代新候选的干净 Windows、安装器和第三方许可证验证。
- 不把可选 7z SFX 视为安装器；Internal Beta 安装器由独立 Inno Setup 配置生成。
- 不承诺 Stable Public Release 日期、商业品牌、公司主体或大规模用户支持。

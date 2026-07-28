# Qt / PySide6 Risk Analysis

- 事实：当前运行库来自与本机 PySide6 wheel 树逐文件 SHA-256 对比的候选证据。
- 事实：项目使用 PyInstaller onedir；Qt DLL 和插件以普通文件保留在 `_internal/PySide6`。
- 推断：普通文件结构技术上支持替换，但尚未完成替换后启动/功能回归，不能宣称 LGPL 可替换义务已完全满足。
- 风险：PyInstaller hook 收集了大量静态代码未导入的 QML/Qt 模块，包括 GPL-only 候选。
- 事实：发行 wheel 范围文件与 4 个精确 PyPI Windows wheel 逐字节一致 = `True`。
- 事实：4 个精确 wheel 归档已保留并通过 PyPI SHA-256 = `True`。
- 事实：22 个实际 Qt 源模块的官方源码归档已下载并通过官方 SHA-256 = `True`。
- 事实：Qt Multimedia attribution 指向的 FFmpeg 7.1.3 精确源码已归档并验证 = `True`。
- 事实：PySide/Shiboken 源码归档已下载并通过官方 SHA-256 = `True`。
- 事实：Qt 官方许可、第三方代码、WebEngine 许可与 SBOM 文档快照已归档 = `True`。
- 结论：本轮 Qt/PySide/Shiboken 许可证与源码材料闭合 = `True`。
- 边界：按所有者决定，本轮不删除 POSSIBLY_UNUSED 或 GPL-only 候选模块；最小化留待独立阶段。

# Third-Party Components

本目录用于 `Qonic Audio v5.0 Internal Test` 的内部测试版发行审核。

Qonic Audio 项目自有代码采用 `GPL-3.0-or-later`，完整许可证文本位于仓库和发行包顶层的 `LICENSE`。本目录只记录第三方组件，不改变各组件原有的版权与许可条件。

## 当前运行 / 打包涉及的第三方组件

- `PySide6 / Shiboken6 / Qt 6.11.1`
  本轮按 Community Edition 的 GPL-3.0 路线审核。四个精确 wheel、22 个实际 Qt 模块源码归档、PySide/Shiboken 源码归档及 Qt 官方许可/第三方代码说明均记录在 `third_party/`；`PySide6-LicenseRef-Qt-Commercial.txt` 仅保留为 wheel 内原始证据，不代表项目采用商业授权。
- `watchdog`
  已附带许可证原文：`watchdog-Apache-2.0.txt`
- `mutagen`
  已附带许可证原文：`mutagen-GPL-2.0.txt`
- `FFmpeg`
  已附带审核说明：`FFmpeg-NOTICE.md`
- `ncmdump`
  已附带上游 MIT 许可证原文和审核说明：`ncmdump-MIT.txt`、`ncmdump-NOTICE.md`

## 构建工具

- `PyInstaller`
  已附带许可证原文：`PyInstaller-GPL-2.0-with-Bootloader-Exception.txt`

## 说明

- 本目录优先保证审核阶段可追踪每个第三方组件的来源和当前已收集到的许可证材料。
- `FFmpeg` 当前 Gyan 8.1.1 full build 的官方资产、资产 SHA-256、核心源码 commit/归档和本地二进制逐字节一致性已闭合；Gyan 未公开完整构建脚本、补丁及静态依赖锁定材料，仍是 BLOCKER。
- `ncmdump 1.5.1` 已附带 MIT 原文；官方 CLI ZIP 内 EXE 与权威发行目录文件逐字节一致，精确 commit 源码、Windows 构建元数据及静态依赖源码均已固定并校验，且未替换现有 EXE。
- 8 个 Microsoft VC Runtime DLL 已单独列项并保存许可条款；需要项目所有者确认当前构建/分发受有效 Visual Studio 或 Build Tools 许可覆盖。

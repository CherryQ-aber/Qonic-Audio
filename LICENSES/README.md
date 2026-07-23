# Third-Party Components

本目录用于 `Qonic Audio v5.0 Internal Test` 的内部测试版发行审核。

Qonic Audio 项目自有代码采用 `GPL-3.0-or-later`，完整许可证文本位于仓库和发行包顶层的 `LICENSE`。本目录只记录第三方组件，不改变各组件原有的版权与许可条件。

## 当前运行 / 打包涉及的第三方组件

- `PySide6`
  当前环境可直接提取到的文件：`PySide6-LicenseRef-Qt-Commercial.txt`。该文件只说明安装包中存在商业许可引用，不能证明当前项目已经取得 Qt 商业授权；`requirements.txt` 使用标准 PyPI 包时，应按 Community Edition 的 LGPLv3 / GPLv3 路径完成审核，或改用 Qt 账号提供的商业包并保存授权凭证。
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
- `FFmpeg` 当前仓库只保留运行所需二进制文件；当前 Gyan full static 构建自报 GPLv3 配置，GPLv3 全文已随顶层 `LICENSE` 提供，正式对外交付前仍应补齐版权声明、精确源码获取与构建来源说明。
- `ncmdump 1.5.1` 已附带上游仓库的 MIT License 文本；仍需保存当前二进制与上游 Windows 发行资产的来源对应证据。
- `PySide6` 当前本地安装目录中仅发现 `LicenseRef-Qt-Commercial` 文本；正式外部分发前，仍建议结合实际授权来源补充完整的 Qt / PySide6 许可材料。

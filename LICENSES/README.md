# Third-Party Components

本目录用于 `Qonic Audio v5.0 Internal Test` 的内部测试版发行审核。

## 当前运行 / 打包涉及的第三方组件

- `PySide6`
  当前环境可直接提取到的文件：`PySide6-LicenseRef-Qt-Commercial.txt`
- `watchdog`
  已附带许可证原文：`watchdog-Apache-2.0.txt`
- `mutagen`
  已附带许可证原文：`mutagen-GPL-2.0.txt`
- `FFmpeg`
  已附带审核说明：`FFmpeg-NOTICE.md`
- `ncmdump`
  已附带审核说明：`ncmdump-NOTICE.md`

## 构建工具

- `PyInstaller`
  已附带许可证原文：`PyInstaller-GPL-2.0-with-Bootloader-Exception.txt`

## 说明

- 本目录优先保证审核阶段可追踪每个第三方组件的来源和当前已收集到的许可证材料。
- `FFmpeg` 和 `ncmdump` 当前仓库只保留运行所需二进制文件，本地未发现随附许可证原文，因此先以说明文件标记，正式对外交付前应补齐对应许可证文本或官方分发说明。
- `PySide6` 当前本地安装目录中仅发现 `LicenseRef-Qt-Commercial` 文本；正式外部分发前，仍建议结合实际授权来源补充完整的 Qt / PySide6 许可材料。

# Qonic Audio 发行策略

## 当前结论

- 项目采用开源路线，项目自有代码以 `GPL-3.0-or-later` 发布。
- 当前版本继续保持 `v5.0 Internal Test`；只有完成本文件的 RC 门禁后，才统一晋级为 `v5.0 RC1`。
- 当前主分发工件为便携版 `.7z`，同时发布 SHA-256 校验清单。
- 7z SFX 只作为可选内部构建验证，不作为 GitHub Release 的主下载。
- 安装器、数字签名、自动更新和文件关联移入 RC 之后的独立计划，不阻塞 RC1。

## RC1 晋级门禁

以下项目全部完成后，才能同时修改版本源、包名、Windows 版本资源和发行说明：

1. 真实桌面人工验收完成，包括四套主题、100% / 125% / 150% DPI、双屏、Snap、托盘和窗口控制。
2. 使用真实媒体完成自动转码、NCM、Metadata、Lyrics、Cover、Pitch、播放器和 no-clobber 回归。
3. 在未安装 Python、FFmpeg、ncmdump 和开发工具的干净 Windows 环境完成异机验收。
4. FFmpeg、ncmdump、PySide6 / Qt 的来源、许可证文本、版权声明和源码获取义务形成可随包审核的材料。
5. 项目著作权标注主体得到确认，避免把品牌名误写成尚未成立的法律实体。
6. Qonic 品牌图标的使用权得到确认。
7. 从干净发行提交构建 `.7z`，通过完整测试、打包后 smoke、`7z t`、SHA-256 和敏感信息扫描。

## RC1 工件建议

推荐 GitHub Release 同时提供：

- `Qonic_Audio_v5.0_rc1.7z`
- `Qonic_Audio_v5.0_rc1-SHA256SUMS.txt`
- 与 tag 对应的源代码归档
- `LICENSE`、`LICENSES/`、Release Notes 和 Known Issues

RC1 不默认发布未签名 SFX `.exe`，降低 SmartScreen 误解和“安装器”认知混淆。安装器与数字签名应在便携版 RC 稳定后单独设计、测试和验收。

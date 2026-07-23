# FFmpeg Notice

当前项目发行包会随包携带：

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ffmpeg/bin/ffprobe.exe`

本仓库当前仅在 `Tools/ffmpeg/` 保存运行所需二进制文件。当前 GPLv3 全文由发行包顶层 `LICENSE` 提供。

当前候选二进制的可核验信息：

- 自报版本：`ffmpeg 8.1.1-full_build-www.gyan.dev`
- SHA-256：`09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73`
- 构建配置包含：`--enable-gpl --enable-version3 --enable-static`
- 二进制提供方页面：`https://www.gyan.dev/ffmpeg/builds/`
- FFmpeg 官方许可说明：`https://ffmpeg.org/legal.html`

审核结论：

- 当前 v5.0 内部测试候选已明确标记 FFmpeg 为随包外部工具。
- Gyan 构建页面明确其 Windows 静态构建使用 GPLv3；正式对外交付前，仍应补齐与当前二进制对应的版权声明、精确源码获取与构建来源说明。

建议至少核对：

- 该二进制具体来源
- 对应许可证类型
- 是否需要附带源码获取方式或官网链接

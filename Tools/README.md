# External Tools

发行构建前需要准备以下文件：

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ncmdump/ncmdump.exe`

`ffplay.exe` 与 `ffprobe.exe` 不是当前程序运行所需文件，不会进入发行包。

这些第三方大型二进制文件不会提交到 Git。分发时需要同时确认对应工具的许可证要求。

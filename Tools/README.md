# External Tools

发行构建前需要准备以下文件：

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ffmpeg/bin/ffprobe.exe`
- `Tools/ncmdump/ncmdump.exe`

`ffprobe.exe` 用于 Pitch 处理前后的媒体、时长和输出校验，必须与 `ffmpeg.exe` 一起进入发行包。`ffplay.exe` 不是当前程序运行所需文件，不会进入发行包。

这些第三方大型二进制文件不会提交到 Git。分发时需要同时确认对应工具的许可证要求。

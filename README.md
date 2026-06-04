# CherryQ Audio Converter

CherryQ Audio Converter 是一个面向 Windows 的本地音频监听、NCM 解码与批量格式转换工具。

当前发行基线：`v3.5.1`

## 核心能力

- 监听指定目录并自动发现新音频文件
- 扫描目录中已经存在的音频文件
- 使用 `ncmdump` 解码 NCM 文件
- 使用 FFmpeg 转换 MP3、FLAC、WAV、M4A、AAC、OGG
- 支持全局、单文件与批量目标格式设置
- 支持失败重试、状态展示与系统托盘操作
- 转换过程保留源文件，输出重名时自动生成新文件名

## 开发环境

```powershell
python -m pip install -r requirements-dev.txt
python gui.py
```

外部工具需要放在：

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ncmdump/ncmdump.exe`

这些大型二进制文件不会提交到 Git，详细说明见 `Tools/README.md`。

## 测试

```powershell
python -m unittest discover -v
```

人工发行回归步骤见 `TEST_CHECKLIST.md`。

## 构建发行版

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

构建脚本使用 `CherryQ Audio Converter.spec`，生成：

- `Release/CherryQ Audio Converter_V3.5.1_release`
- `Release/CherryQ Audio Converter_V3.5.1_release.7z`
- `Release/CherryQ Audio Converter_V3.5.1_release.exe`

发行目录不会携带开发机的 `config.json`，首次启动会使用程序目录作为默认输出位置。

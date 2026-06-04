CherryQ Audio Converter v3.5.1
================================

这是 CherryQ Audio Converter v3 系列的修复发行基线。

首次使用
--------
1. 双击 CherryQ Audio Converter.exe。
2. 按提示选择需要监听的音频目录。
3. 在设置区确认输出目录和目标格式。
4. 可选择“扫描已有文件”，或保持程序监听新下载的文件。
5. 文件进入“等待处理”状态后，点击“开始转换”。

重要行为
--------
- 程序不会删除源音频文件。
- 同格式处理会复制文件到输出目录。
- 输出目录存在同名文件时，会自动生成“文件名 (1)”等新文件，不覆盖旧结果。
- 程序退出时会等待当前转换安全结束；若 30 秒内未结束，将取消退出。

支持
----
- 输入：NCM、MP3、FLAC、WAV、M4A、AAC、OGG
- 输出：MP3、FLAC、WAV、AAC、OGG

发行包内容
----------
- CherryQ Audio Converter.exe
- _internal：程序运行依赖、ffmpeg.exe、ncmdump.exe
- Music_Output：默认输出目录
- logs：运行日志目录
- README.txt：本说明

注意事项
--------
- 本版本为免安装目录版，不需要用户安装 Python 或 FFmpeg。
- 请保留整个程序目录，不要单独移动主程序 exe。
- 首次启动不会携带开发电脑的路径配置。
- 当前版本未提供数字签名、自动更新和正式安装器。

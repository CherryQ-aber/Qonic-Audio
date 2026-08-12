# Qonic Audio 异机测试说明

## 测试包定位

- 软件：Qonic Audio Converter & Editor
- 版本：5.0.0-beta.1
- 发行渠道：Internal Beta / GitHub Pre-release（如发布）
- 平台：Windows x64
- 形式：免安装 `.7z` 便携测试包

本测试包不是安装器，当前没有数字签名、自动更新或文件关联。请不要把它作为正式稳定版转发。

## 开始前

1. 将 `.7z` 和同目录的 `SHA256SUMS.txt` 放在一起。
2. 在 PowerShell 中计算校验值：

   ```powershell
   Get-FileHash -Algorithm SHA256 .\Qonic_Audio_v5.0_internal_test.7z
   ```

3. 确认结果与 `Qonic_Audio_v5.0_internal_test-SHA256SUMS.txt` 一致。
4. 使用 7-Zip 解压到普通用户有写权限的目录，例如桌面或文档目录；不要解压到 `Program Files`。
5. 运行解压目录中的 `Qonic_Audio_v5.0_internal_test.exe`。

测试电脑不需要预装 Python、FFmpeg 或 ncmdump。不要为了通过测试而关闭 Windows Defender；若出现 SmartScreen 或安全软件提示，请记录提示文字和截图。

## 最小验收矩阵

请记录 Windows 版本、x64 架构、屏幕缩放比例、显示器数量、音频输出设备和安全软件结果。

### 启动与窗口

- 首次启动可以显示 Qonic Audio 主界面，没有缺失 DLL、QML 插件或终端窗口闪现。
- 100% / 125% / 150% DPI 下检查裁切、重叠和不可达控件。
- 验证窗口拖动、八边缩放、最大化还原、Windows 11 Snap、最小化、关闭到托盘、托盘恢复和退出。
- 依次检查 dark / light / black / purple 四套主题。

### 自动转码

- 使用可公开测试的小样本验证 MP3、FLAC、WAV、M4A、AAC、OGG、OPUS；如有合法 NCM 样本再验证 NCM。
- 验证单个、选中和全部转换，失败重试与取消。
- 验证中文、空格和跨盘输出路径。
- 确认已有目标不会被覆盖，源文件不会被移动、删除或修改。

### 音频编辑与播放

- 验证播放、暂停、停止、进度跳转、播放结束和输出设备。
- 修改 Metadata、歌词或封面后，默认导出为新副本。
- 验证导入 `.lrc`、Pitch 试听、Pitch 正式导出和显式加载结果。
- 验证切换文件时“放弃修改并载入 / 导出 / 取消”三个分支。

### 设置与退出

- 修改输出目录和主题相关设置，确认保存后重启仍可读取。
- 退出前确认没有残留 Qonic Audio、FFmpeg 或 ncmdump 进程。

## 反馈材料

出现问题时请提供：

- Windows 版本、DPI、显示器数量和音频设备；
- 操作步骤、预期结果和实际结果；
- 完整错误文字与截图；
- `%LOCALAPPDATA%\Qonic Audio\Logs\runtime.log`；
- 发生问题的文件格式、大小和是否跨盘。

不需要发送包含隐私或版权内容的原始音频。若问题只能由特定文件触发，可以先提供文件容器、编码、时长和脱敏后的日志。

## 测试后清理

Qonic Audio 当前是便携版，不写入安装器注册信息。确认不再需要输出文件后，可以直接删除整个解压目录；删除前请自行保留需要的 `Music_Output`、`AudioEditor_Output`、配置和日志。

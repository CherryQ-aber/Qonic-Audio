# Qonic Audio

**Qonic Audio Converter & Editor** 是一个面向 Windows 的本地音频处理工具，包含“自动转码”和“音频编辑”两个工作区。

当前版本：`v5.0 Internal Test`
当前阶段：`v5.0 内部测试版`

> 这是 UI 重构后的内部人工测试基线，不是正式对外发行版。QML 主界面与旧 Widgets 界面目前并存；User Trial Mode 只供人工验收，不能视为最终用户流程。

## v5.0 内部测试版定位

- 验收 QML 工作台的受控扫描、队列、转换、watcher、设置保存与既有音频编辑链路。
- 保持 `CapabilityGate`、no-clobber 发布、源文件保护和显式写入确认；`QONIC_QML_LIVE=1` 不能自行授予真实能力。
- 冻结 Phase 5.7 的业务范围。下一阶段优先重组普通用户的任务流程，而不是继续增加能力或按钮。
- 完整范围和当前人工验收结论见 `docs/UI_REFACTOR_CHANGE_SUMMARY.md`、`docs/PHASE_5_7_CLOSEOUT.md` 与 `Known_Issues.md`。

## 主要功能

### 自动转码区

- 监听目录、扫描已有文件、拖入文件快速入队
- NCM 解码与普通音频格式转换
- 全局、单文件、批量目标格式设置
- 输出重名递增保护
- 可选按目标格式创建子文件夹
- 本轮“转换到...”临时输出目录
- 转换后查找同名 `.lrc/.LRC`
- 可写入 MP3 / FLAC / M4A / OGG 内嵌歌词
- 可选复制外置 `.lrc`
- 失败重试、终态清理、系统托盘运行

### 音频编辑区

- 导入 / 拖入普通音频
- 内置播放器：播放、暂停、停止、进度跳转、音量控制
- 当前文件栏与当前播放源提示
- 文件信息整理：标题、艺术家、专辑、年份、风格、轨道号
- 封面读取、导入、移除、恢复、写入
- 歌词读取、手动导入、编辑、另存为 `.lrc`、保存到原 `.lrc`
- 内嵌歌词优先读取，不自动被外部 `.lrc` 覆盖
- 写入当前音频歌词，并在写入前临时释放播放器媒体源
- 升降调试听、返回当前文件播放、导出为新文件

## 支持格式

- 自动转码输入：`NCM / MP3 / FLAC / WAV / M4A / AAC / OGG / OPUS / APE / AIFF / AIF / WMA`
- 自动转码输出：`MP3 / FLAC / WAV / AAC / M4A / OGG / OPUS`
- 音频编辑导入：`MP3 / FLAC / WAV / M4A / AAC / OGG / OPUS / APE / AIFF / AIF / WMA`

## 使用方式

### 自动转码区

1. 首次启动后先选择监听目录和输出目录。
2. 选择目标输出格式，按需开启歌词写入和外置 `.lrc` 保留。
3. 通过监听、扫描已有文件或拖入文件把任务加入队列。
4. 点击“开始转换”或“转换到...”执行本轮转换。

### 音频编辑区

1. 导入一个普通音频文件。
2. 先检查音频信息、封面和歌词读取结果。
3. 再执行歌词写入、封面写入、元数据写入或升降调试听 / 导出。

## 外部工具

程序依赖以下随包携带的工具：

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ncmdump/ncmdump.exe`

开发环境中也需要这两个文件放在上述路径。详细说明见 `Tools/README.md`。

## 依赖

运行依赖：

- `PySide6`
- `watchdog`
- `mutagen`

开发 / 打包附加依赖：

- `PyInstaller`

## 测试

自动化测试：

```powershell
python -m pytest -q
python -m unittest discover -v
```

人工回归清单见 `TEST_CHECKLIST.md`。
当前未解决事项见 `Known_Issues.md`。

## 构建发行版

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

当前构建脚本使用 `Qonic_Audio.spec`。v5.0 内部测试版构建通过后将生成：

- `Release/Qonic_Audio_v5.0_internal_test`
- `Release/Qonic_Audio_v5.0_internal_test.7z`
- `Release/Qonic_Audio_v5.0_internal_test.exe`

发行目录不会携带开发机的 `config.json`，而是附带 `config.example.json` 作为示例配置。

## 常见问题

- 首次启动默认监听目录不存在：程序会提示你重新选择，不会因为默认网易云路径失效而崩溃。
- 写入歌词、封面或元数据出现 `Permission denied`：通常是播放器或其他程序仍占用文件，程序会先尝试释放自身播放器媒体源再重试。
- 某些格式无法预览：QtMultimedia 的解码能力会受到系统环境影响。

## 已知限制

- 波形图暂未开放
- 自动调式识别暂未开放
- BPM 检测暂未开放
- 不开放覆盖原音频内容
- WAV 的元数据 / 歌词兼容性有限
- 某些播放器不一定能识别内嵌歌词或封面

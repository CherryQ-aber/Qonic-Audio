# Qonic Audio

**Qonic Audio Converter & Editor** 是一个面向 Windows 的本地音频处理工具，包含“自动转码”和“音频编辑”两个工作区。

当前版本：`5.0.0-beta.1`

当前发行渠道：`Internal Beta`

项目类型：`Personal Software Project`

> 本项目是持续开发中的个人音频软件项目，主要用于开发者本人长期使用及有限测试。项目可以提供 Windows 预发布构建，但目前不存在 Official Stable Public Release。

## 开源与分发

- Qonic Audio 项目自有代码采用 `GPL-3.0-or-later`，完整条款见 `LICENSE`。
- 第三方组件继续遵循各自许可证，来源和审核材料见 `LICENSES/`。
- 当前主发行渠道为 Internal Beta；GitHub 二进制构建如发布，必须标记为 **Pre-release**。
- 当前 `v5.0.0-beta.1` 安装器已经作为 GitHub **Pre-release** 发布；这不改变 Internal Beta 定位。
- 安装器继续作为核心工程能力；便携版 `.7z` 可作为受控测试工件。
- 数字签名、自动更新与文件关联属于可选增强，不阻塞当前 Internal Beta。
- Qonic 仅是 working/project name；Public commercial brand 为 `NOT FROZEN`，Qonance 未采用，正式商标清查延后到未来明确规划 Official Public Release 时。
- 当前状态与发行规则分别以 `docs/PROJECT_STATUS.md` 和 `docs/RELEASE_STRATEGY.md` 为准。

## Internal Beta 定位

- 验收 QML 工作台的受控扫描、队列、转换、watcher、设置保存与既有音频编辑链路。
- 保持 `CapabilityGate`、no-clobber 发布、源文件保护和显式写入确认；`QONIC_QML_LIVE=1` 不能自行授予真实能力。
- Internal Beta 不限制后续功能迭代，但不承担 Stable Public Release、商业品牌或大规模用户支持承诺。
- 完整范围和当前人工验收结论见 `docs/UI_REFACTOR_CHANGE_SUMMARY.md`、`docs/PHASE_5_7_CLOSEOUT.md` 与 `Known_Issues.md`。

## 仓库主线与验证

- `main` 是长期 canonical development branch，承接已验收的 `codex/v5_P1` 开发历史；`codex/v5_P1` 暂时保留为历史开发分支。
- 校正前的旧 `main` 由远程分支 `archive/main-pre-v5-realignment` 保留，不通过 unrelated-histories merge 拼接两套历史。
- `.github/workflows/ci.yml` 在 Windows 上验证 post-install 用户状态、设置存储、运行模式、能力门、主题和窗口逻辑；触发范围为对 `main` 的 push 和 pull request。
- `compliance.yml`、`ffmpeg-build.yml` 与 `ffmpeg-compliance.yml` 继续承担重量级依赖合规及 FFmpeg 验证，不并入普通 push 的快速测试。

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
- `Tools/ffmpeg/bin/ffprobe.exe`
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
安装态用户状态验收记录见 `docs/POST_INSTALL_USER_STATE_ACCEPTANCE.md`。
异机便携包的使用和反馈格式见 `EXTERNAL_TEST_GUIDE.md`。
当前未解决事项见 `Known_Issues.md`。

## 构建发行版

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

当前构建脚本使用 `Qonic_Audio.spec`。Internal Beta 构建通过后将生成：

- `Release/Qonic_Audio_v5.0.0-beta.1`
- `Release/Qonic_Audio_v5.0.0-beta.1.7z`
- `Release/Qonic_Audio_v5.0.0-beta.1-SHA256SUMS.txt`

`.7z` 是当前默认和主分发工件。如需内部验证 7z SFX，可显式执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -IncludeSfx
```

SFX `.exe` 仅供内部验证，不等同于安装器。

构建可安装的 Internal Beta 候选：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

安装器脚本只接受已经验证的 Internal Beta onedir（默认查找 `Release/Internal_Beta_Candidates`，也可用 `-ApplicationSource` 显式指定），避免把未完成 Qt LGPL route 验证的原始 PyInstaller collection 误包为分发安装器。它提供 Program Files 安装、开始菜单入口、可选桌面快捷方式与卸载。构建需要 Inno Setup 6；缺少编译器时必须记录为 `NOT RUN`。

安装器根据 Windows UI 语言自动选择简体中文或英文，不额外显示语言选择窗口；中文 Windows 使用简体中文，其他未提供翻译的语言环境回退英文。产品名、版本号和 `Internal Beta` 渠道标识保持统一英文元数据。

发行规范以 `main_qml.py` 为唯一产品入口，旧 `gui.py` 不进入 v5.0 主程序。可执行文件包含 Qonic Audio 产品名、完整说明和内部测试版本属性。构建脚本会检查自有 QML、图标、GPL 项目许可证、FFmpeg 和 ncmdump，运行打包后离屏 smoke，并在生成归档时写出 SHA-256 清单。

发行目录不会携带开发机的 `config.json`，而是附带 `config.example.json` 作为示例配置；顶层 `LICENSE` 和 `LICENSES/` 会一并进入发行包。已安装/冻结运行时的配置、缓存、日志和临时数据位于 `%LOCALAPPDATA%\Qonic Audio`，不会写入 Program Files；默认用户输出位于用户 Music 目录。

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

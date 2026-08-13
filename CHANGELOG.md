# Qonic Audio Changelog

## 5.0.0-beta.1 — Internal Beta

### Changed

- 建立公开仓库卫生政策、tracked/candidate-file scanner 与 Core CI 门禁；本地 Codex/Agent 记录、配置、媒体、日志、缓存、审查包和构建工作区不进入 GitHub。
- Core CI 从稳定子集升级为完整 pytest 回归，并保留独立的重量级 Compliance / FFmpeg workflows。
- 补全封面读取与验证实际使用的 Pillow 12.2.0 运行依赖，使干净 Windows CI 环境能够收集并运行完整测试套件。
- Core CI 从已发布 Internal Beta 安装器临时提取并逐项校验固定 SHA-256 的 Qonic FFmpeg/FFprobe，仅用于 runner 的真实媒体回归，不把二进制提交回源码仓库。
- 第三方合规收尾工具支持显式 `--python-runtime-root`，或从当前 CPython 环境安全探测 runtime root；使用前验证 CPython 3.12.1、可执行文件与 `LICENSE.txt`，不再依赖固定 Windows 用户安装路径。
- Windows 安装器确立为长期 Internal Beta 的主要安装与分发方式；便携 `.7z` 仅作为可选受控测试或诊断工件。
- 建立统一 App Paths：配置、缓存、日志分别使用 `%LOCALAPPDATA%\Qonic Audio\Config`、`Cache` 与 `Logs`；源码运行可用 `QONIC_USER_DATA_ROOT` 隔离测试配置。
- 旧 EXE/项目同目录配置与早期 LocalAppData 根配置改为一次性只读迁移；迁移保留未知字段、不删除旧文件，并避免升级用户被误判为 First Run。
- QML 主题改为即时原子保存并跨重启恢复；窗口保存 normal geometry 与 maximized 状态，首次居中并在显示器移除/分辨率变化时回到有效区域。
- 正式 QML 入口新增轻量 First Run 目录确认，支持单/多候选、另选目录与暂时跳过；接受目录只保存设置，不启动监听或转换。
- 项目正式重定位为长期维护的 `Personal Software Project / Internal Beta`；当前不存在 Stable Public Release。
- `app_info.py` 新增独立 Release Channel 与项目分类，窗口/版本属性/包名统一为 `5.0.0-beta.1 · Internal Beta`。
- 发行策略改为 Development → Internal Validation → Internal Beta → optional GitHub Pre-release；原 RC/Public Stable 项目改为延后 Gate。
- Qonic 只作为 working/project name；Brand NOT FROZEN，Qonance NOT ADOPTED，商标与商业品牌清查延后到未来明确规划 Official Public Release 时。
- 冻结运行时的配置、缓存、日志与临时数据迁移到 `%LOCALAPPDATA%\Qonic Audio`；旧便携配置仅在新配置不存在时复制，用户自选路径保持不变。
- 新增基于 Inno Setup 的可复现安装层，继续包裹现有 PyInstaller onedir，提供 Program Files、开始菜单、可选桌面快捷方式与卸载；用户数据在卸载/升级时保留。
- Internal Beta Gate 与 Public Stable Deferred Gate 分离；第三方许可证、Runtime inventory、Notices、对应源码与 SHA-256 要求不降级。

### Preserved

- 未修改音频算法、转码逻辑、播放器架构、QML 页面结构、FFmpeg 构建、Qt Runtime 裁剪和历史发行/合规证据。

### Built

- 使用 Inno Setup 6.7.3 从已验证 LGPL candidate 生成 `Qonic_Audio_v5.0.0-beta.1_Setup.exe`；版本资源标记 `5.0.0-beta.1 / Internal Beta`。
- 2026-08-13 从包含 Post-Install User State 修复的新 PyInstaller onedir 重建 LGPL portable 与安装器候选；portable SHA-256 为 `6408218ECBC710160A6008CB7999BBD70C8AF0C5A29BDC38119F4807241C8A15`，安装器 SHA-256 为 `544F9762D07B3BEB3FD8C271D4558E6CD084BD3655C4FC631F605BBB97EE225C`。
- 当前安装器按 Windows UI 语言自动选择简体中文或英文，不显示额外语言选择框，并随安装目录提供 Inno Setup 许可证。
- 首个纯英文安装器 SHA-256 `7F1FFBB1C2CCB9A27D6EAC638A0A356647907FEDCE9EAA18573EF771F7C5302E` 已归档为 `NONAUTHORITATIVE / NOT FOR RELEASE`。
- 构建脚本支持 winget 按用户安装的 Inno Setup、深层 Qt 路径临时盘符缩短、集中版本号派生和随包 SHA-256 文件。真实安装/升级/卸载验收未在本步骤执行。

## v5.0 内部测试版

### Changed

- 产品品牌由 `CherryQ Audio Converter` 迁移为 `Qonic Audio`，完整说明统一为 `Qonic Audio Converter & Editor`。
- 运行日志、打包名称、规范文件、临时文件标记和新环境变量统一使用 `Qonic` / `QONIC_*`；旧 `CHERRYQ_*` 环境变量仅保留迁移期兼容。
- PyInstaller 发行入口由旧 `gui.py` 切换为 `main_qml.py`，并显式携带 `ui_next/qml` 与应用图标运行时资源。
- 发行脚本新增打包后 QML smoke、QML 入口/图标检查和归档 SHA-256 清单。
- 项目开源许可确定为 `GPL-3.0-or-later`，顶层许可证和第三方许可材料纳入发行包。
- `.7z` 确定为当前默认主分发工件；SFX 改为显式 `-IncludeSfx` 的内部验证选项，不作为主下载。
- 安装器、数字签名、自动更新和文件关联延期到 RC 之后的独立计划。
- 新增 RC1 晋级门禁，当前版本在人工桌面、真实媒体、干净 Windows 和第三方合规完成前继续保持 Internal Test。
- 新增异机便携包测试说明，覆盖校验、解压、环境记录、最小功能矩阵、日志反馈和测试后清理。
- Windows 可执行文件补充 Qonic Audio 产品名、完整说明、内部测试版本和原始文件名属性。
- 项目定位调整为 `v5.0 Internal Test / v5.0 内部测试版`：用于 UI 重构后的内部人工验收和代码审查，不是正式对外发行。
- 版本源、窗口标题、打包目录名和发行说明文件名统一由 `app_info.py` 管理为 `Qonic_Audio_v5.0_internal_test`。
- 归档 UI 重构后的完整变更总结，覆盖 Legacy Widgets 收口、QML 工作台、能力门、会话边界、真实业务回归和 User Trial Mode。
- Phase 5.9.2 将单一任务队列扩展为转码控制中心：任务可控制本轮参与、单独目标格式和临时输出目录，并可转换单个、选中或全部已启用任务。
- 队列多选和右键操作使用规范化路径，不依赖表格行号；格式菜单复用统一格式注册表，所有转换继续复用既有 `ConvertThread`。

### Frozen

- Phase 5.9.5 工作区与普通用户任务流整合已完成；发行收尾期间冻结新功能和大范围导航改造。
- `CapabilityGate`、默认 Preview Mode、no-clobber 发布、源文件保护、显式配置保存和三类会话边界继续有效。
- “本轮跳过”保持为独立内存策略，不成为任务终态；任务级输出目录不写全局配置。

### Fixed

- 修复真实 AppShell 测试销毁时未等待设置存储扫描线程，导致 `Qt6Core.dll / 0xc0000409` 的套件级崩溃。
- 修复转换前输出目录校验忽略任务快照目录的问题；任务已经记录有效输出目录时，不再被缺失的全局默认目录错误阻止。
- 补回 Pitch 处理运行时必需的 `ffprobe.exe`，避免开发机可用而异机包无法完成媒体和时长校验。

## v4.1 beta / 内部测试版

### Changed

- 音频编辑区进入 v4.1 beta 收口阶段，窗口标题与应用版本口径统一为 `CherryQ Audio Converter v4.1 beta`。
- 播放输出设备选择迁移到当前文件栏右上角，并保持下拉展开前刷新设备列表的交互。
- 自动转码区缓存管理、歌词右键菜单、封面右键菜单、播放进度条菜单和播放设备下拉列表进入回归测试收口。

### Fixed

- 统一右键菜单与下拉菜单的禁用、悬停和选中态视觉细节。
- 保持播放设备刷新不触发设备切换，降低播放中反复刷新 / 重绑定导致卡顿的风险。

## v4.0 RC / 内部测试版

### Added

- 新增音频编辑工作区，提供独立于自动转码队列的单曲编辑流程。
- 新增内置播放器，支持导入、拖入、播放、暂停、停止、进度跳转与音量控制。
- 新增文件信息整理能力，支持读取、编辑并写入标题、艺术家、专辑、年份、风格、轨道号等基础元数据。
- 新增封面读取、预览、导入、移除、恢复和写入能力。
- 新增歌词读取、手动导入、编辑、另存为 `.lrc`、保存到原 `.lrc` 与写入当前音频能力。
- 新增升降调试听与导出为新文件能力，并尽量保留基础元数据与封面。
- 新增版本集中定义文件 `app_info.py`，统一窗口标题、发行目录名、可执行文件名和发行说明文件名。
- 新增 `Release_Notes_v4.0.md`、`Known_Issues.md`、`config.example.json` 与 `LICENSES/README.md` 作为发行审核文件。

### Changed

- 自动转码区支持监听目录、扫描已有文件和拖入文件后的快速入队，再由后台线程完成验证与准备。
- `.ncm` 解码统一走程序内部临时目录，避免在原始下载目录残留中间产物。
- 输出路径策略统一支持按目标格式创建子文件夹、同名递增和本轮“转换到...”临时输出目录。
- 转换后歌词处理拆分为“写入内嵌歌词”和“复制外置 `.lrc`”两个独立选项，默认不覆盖已有歌词。
- 音频编辑区歌词来源优先级调整为“内嵌歌词优先，外部 `.lrc` 需要显式导入或确认同步”。
- 写入歌词、封面、元数据前会先释放播放器媒体源，降低 `Permission denied` 风险。
- PyInstaller 发行命名统一为 `CherryQ_Audio_Converter_v4.0`。

### Fixed

- 修复同格式处理时误移动源文件的问题，改为复制源文件，避免误删原文件。
- 修复输出文件已存在时的覆盖风险，改为自动生成递增文件名。
- 修复部分切换音频后残留上一首信息、封面或歌词的风险。
- 修复导出或写入后播放器未正确恢复当前文件源的场景。
- 修复音频编辑区部分小窗口布局拥挤、歌词区过窄和按钮挤压问题。

### Known Limits

- 波形图暂未开放。
- 自动调式识别暂未开放。
- BPM 检测暂未开放。
- 不开放直接覆盖原音频内容。
- WAV 的元数据和歌词兼容性有限。
- 某些播放器或系统环境下，QtMultimedia 的解码能力可能有限。
- 升降调处理速度取决于音频文件大小与当前机器性能。

## v3.5.1

- 建立 v3.5.1 稳定发行基线。
- 加入自动化测试、依赖清单、发行说明和可复现打包脚本。
- 修复同格式处理保留源文件、输出重名保护、AAC / OGG 输入支持和退出时转换线程安全结束。

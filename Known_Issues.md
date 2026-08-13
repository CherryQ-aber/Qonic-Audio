# Qonic Audio 5.0.0-beta.1 Internal Beta — Known Issues

本文件记录当前 Internal Beta 仍未闭合的问题。项目没有 Official Stable Public Release。

## Internal Beta Gate 仍需跟进

- `5.0.0-beta.1` 安装器已使用 Inno Setup 6.7.3 编译并完成版本/SHA-256 核验；主题持久化、窗口位置/大小/最大化状态恢复、First Run 和用户配置目录迁移的安装态人工验收均为 PASS。完整卸载、所有安装器语言路径与完整 clean-machine release gate 仍未完全覆盖。
- 安装器已配置随 Windows UI 语言自动选择简体中文或英文，当前 `zh-CN` 环境预期使用简体中文；真实向导显示与升级时重新检测语言仍待随安装验收人工确认。
- 当前安装器未进行数字签名，状态为 `NotSigned`；按 Internal Beta Policy 属于可选增强，不是当前硬阻塞项。
- `%LOCALAPPDATA%\Qonic Audio` 数据分离和旧便携配置的一次性、非破坏迁移已作为当前安装态工作基线通过人工验收；后续修改必须保持该行为。
- `v5.0.0-beta.1` 已作为 GitHub Pre-release 发布。后续新候选仍需复跑完整自动化、打包后 QML smoke、真实媒体和适用的干净 Windows 验收；旧 v5.0/r4 结果仅作历史支持证据。
- 真实 AppShell 测试曾因销毁时遗漏等待设置存储扫描线程而触发 `Qt6Core.dll / 0xc0000409`；测试清理现已与生产退出顺序对齐，完整回归恢复通过。正式候选仍需继续观察退出时后台线程和子进程是否全部收尾。
- 项目自有代码采用 `GPL-3.0-or-later`。当前最终第三方审查为 0 BLOCKER、2 WARNING；所有许可证、通知、源码可得性与运行时清单要求继续适用于 Internal Beta。
- 源码中 QML 与 Legacy Widgets 继续并存，但 v5.0 发行规范只打包 QML 主入口；旧 `gui.py` 仅作为兼容开发入口，不得再作为 v5.0 对外可执行入口。

## 延后与可选事项

- Brand/Trademark/Company/Commercial signing/Stable channel/marketing/store/public support 均为 `DEFERRED — PUBLIC RELEASE ONLY`，不阻塞 Internal Beta。
- 自动更新、Crash reporting、签名、文件关联和 Release automation 为可选增强。
- Qonic 是工作名称，Public commercial brand 尚未冻结；Qonance 未采用。
- 任务状态暂不持久化：任务队列仍以内存状态为主，程序重启后不会恢复上一次的任务队列。

## 当前可接受限制

- 波形图暂未开放。
- 自动调式识别暂未开放。
- BPM 检测暂未开放。
- 不开放直接覆盖原音频内容。
- WAV 的元数据和歌词兼容性有限。
- 某些播放器或系统环境下，QtMultimedia 的解码能力可能有限。
- 升降调处理速度取决于音频文件大小与当前机器性能。

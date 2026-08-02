# Qonic Audio Third-Party Compliance Audit

> 第二阶段执行结果。本文是技术证据报告，不是法律意见；存在 BLOCKER 时不得表述为“完整合规”。

## 1. 执行摘要

- 项目正式名称为 `Qonic Audio`，旧名称 `CherryQ Audio Converter` 只可出现在历史证据中。
- 唯一权威工件：`Release/External_Test/2026-07-30_audio-validation-fix/Qonic_Audio_v5.0_internal_test.7z`。
- 权威归档 SHA-256：`BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4`；所有者冻结值：`BB0967E85AF2857C23587F3CEF37C37D14ED4E4106B7261F21E2F247B47F42F4`。
- 权威工件校验：`True`；同版本候选分叉：`False`。
- 当前结论：`0` 个 BLOCKER、`4` 个 WARNING。

## 2. 当前发行结构

- 正式结构继续固定为 PyInstaller `onedir`，未引入 onefile。
- 权威归档及其对应展开目录是本报告唯一输入。
- 旧 Gyan Runtime 仅保留在 `Release/Non_Authoritative/2026-07-28_b5-former-gyan/` 作为可回滚证据；旧权威归档已标记 `SUPERSEDED_HISTORICAL_NOT_FOR_RELEASE`。
- 构建中间目录不属于发布候选，不纳入权威身份判断。

## 3. 实际第三方二进制清单

- 权威展开目录含 FFmpeg、ffprobe、ncmdump、PySide6/Shiboken6、Qt DLL/QML/plugins 和 Microsoft VC Runtime。
- FFmpeg 运行路径为 `Tools/ffmpeg/bin/ffmpeg.exe`，Pitch 探测使用同目录 `ffprobe.exe`。
- ncmdump 运行路径为 `Tools/ncmdump/ncmdump.exe`，由子进程调用。
- Qt/PySide/Shiboken 已建立逐文件 SHA-256 清单；实际扫描 `2848` 个文件。

## 4. FFmpeg 调查结果

- 当前版本：`63d9c74`；分类：`FFmpeg-GPL-CANDIDATE`。
- 运行时路线：Qonic Audio Runtime 自构建；两份正式 EXE 与获批候选 SHA-256 一致。
- 上游/候选资产：Qonic B5 获批候选；不依赖第三方预构建资产。
- 身份与来源链：正式运行时与获批候选一致；对应源码包、锁文件、脚本、补丁目录和许可证材料均已校验。
- FFmpeg 核心源码 commit：`239f2c733de417201d7ad3b3b8b0d9b63285b2b1`；源码 SHA-256：`2B3A9A878B46050CACA71253C1E43F6239DE91C5C5C59DC72F8F2E0306A5C35A`。
- 提供者公开确认的环境：`fixed Docker Desktop linux/amd64 build environment`。
- 官方包内 README SHA-256：`UNKNOWN`；已恢复 `7` 条外部库版本记录。
- 结论：B5 已完成正式替换、onedir、归档、三个打包 smoke 与完整回归；该 Runtime 仅适用于 Qonic Audio Converter，未来视频需独立受控构建。 `exact_source_closed = True`。

## 5. ncmdump 调查结果

- 本地 EXE 自报版本：`1.5.1`；SHA-256：`A1F6F6CE87500B7B1F2A89DBF85B13E81D327EEA4641DAF8AFE0AB840F2C518C`。
- 正确 CLI 资产应为 `ncmdump-1.5.1-windows-amd64.zip`，官方 SHA-256：`BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC`。
- 用户提供资产：`ncmdump-1.5.1-windows-amd64.zip`；SHA-256：`BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC`。
- 比对状态：`BYTE_IDENTICAL`；`byte_identical_to_upstream = True`。
- 精确源码 commit：`76a55d862f767ee20ae417ecd128fde442eea77f`；源码 SHA-256：`70D1C692130B0C0C53276417FD6246C02C4C39D057005F0435FF4942C7CFF11E`；校验：`True`。
- Windows 构建：`GitHub Actions windows-latest; CMake Release; VCPKG_TARGET_TRIPLET=x64-windows-static`；vcpkg baseline：`a62ce77d56ee07513b4b67de1ec2daeaebfae51a`。
- 结论：官方 CLI ZIP 内 EXE 与权威发行目录文件逐字节一致，保留当前 ncmdump.exe，未执行解压覆盖或替换。

## 6. PySide6 / Qt 调查结果

- PySide6 `6.11.1`，Shiboken6 `6.11.1`。
- 四个精确 wheel 的官方文件名、URL、大小与 SHA-256 已固定；wheel 范围内 `2840/2840` 个文件逐字节一致。
- `22` 个实际 Qt 模块的官方源码归档及 SHA-256 已固定；PySide/Shiboken 对应源码归档已保存并验证。
- Qt Multimedia wheel 内 FFmpeg DLL 已单独归属为官方 attribution 指定的 FFmpeg 7.1.3；精确源码 commit/归档与 SHA-256 已保存，不再错误归入 Gyan 8.1.1 外部工具。
- Qt 官方许可、Qt 内部第三方代码、Qt WebEngine 第三方代码和 SBOM 文档已保存；`materials_closed = True`。
- `18` 组 GPL-only 候选与 `126` 组 `POSSIBLY_UNUSED` 按所有者决定保留；本轮未做模块最小化。

## 7. 当前许可证文件状态

- 项目自有代码采用 `GPL-3.0-or-later`。
- FFmpeg 按 GPL-3.0-only 路线记录；Qonic 自构建包含精确源码、许可证、版权声明、锁文件、配置、补丁目录、脚本和重建说明。
- ncmdump MIT 原文、官方 CLI 资产、精确 commit 源码和静态依赖材料已归档并校验。
- Qt/PySide/Shiboken 按 Community Edition GPL-3.0 路线记录，精确 wheels、源码和官方许可材料已闭合。
- `11` 个 Microsoft VC Runtime 文件已按完整 onedir 范围单列，许可条款与本机/包内审计证据见 `docs/compliance/MICROSOFT_VC_RUNTIME_LICENSE_CONFIRMATION.md`；仍需所有者确认分发许可覆盖。
- 补充扫描发现的 NumPy、Pillow 与 charset-normalizer 不属于本轮三组核心闭环；其许可证状态仍待独立验证，严格校验会保留 WARNING。

## 8. 已确认的事实

- 唯一发行工件、对应展开目录和 SHA-256 已冻结并通过检查。
- FFmpeg/ffprobe 与获批 Qonic 候选逐字节一致。
- FFmpeg、Rubber Band 和全部静态依赖源码及对应源码包 SHA-256 已固定。
- 当前 ncmdump.exe 与官方 1.5.1 Windows amd64 CLI 资产逐字节一致。
- ncmdump 精确源码、Windows 构建工作流、vcpkg baseline、TagLib 2.0.2、zlib 1.3.1 与 utfcpp 4.0.6 已固定。
- Qt 精确 wheels、实际模块源码和官方许可材料已建立可复核清单。
- Qt Multimedia FFmpeg 7.1.3 attribution、版权、许可证与精确源码已建立可复核清单。

## 9. 尚未确认的事实

- FFmpeg Runtime 未来的视频能力需求；该事项必须在独立受控构建阶段重新审核。
- ncmdump 官方 GitHub Actions 的具体 runner 镜像版本与编译器补丁版本未在 Release 元数据中固定。
- Microsoft VC Runtime 的当前构建/分发是否由有效 Visual Studio 或 Build Tools 许可覆盖。
- NumPy、Pillow、charset-normalizer 的精确打包来源、必要性和最终许可证材料。
- Qt 模块真正最小集合；该事项已明确推迟到独立阶段。

## 10. 阻断问题

- 无。

## 11. 普通警告

- `FFMPEG_SELF_BUILD_B5_VERIFIED`：正式发行已采用获批并验证的 Qonic Audio Runtime 自构建；B5 onedir、归档、Corresponding Source、打包 smoke 与完整回归均已通过。
- `QT_GPL_ONLY_MODULES_RETAINED`：发行包包含 18 组 GPL-only 模块；项目采用 GPL-3.0 路线，所有者决定本轮保留并推迟最小化。
- `QT_POSSIBLY_UNUSED_MODULES`：发行包包含 126 组 POSSIBLY_UNUSED Qt/QML/插件模块。
- `MSVC_REDISTRIBUTION_LICENSE_CONFIRMATION`：11 个 Microsoft VC Runtime 文件已按 Visual Studio 2026 REDIST 清单单列；仍需项目所有者确认 Microsoft Visual Studio Community 2026 许可或其它适用再分发权利。

## 12. 本阶段已自动完成的整改

- 冻结并验证唯一权威归档与展开目录。
- 隔离同名不同内容旧工件并标记 `NOT_FOR_RELEASE`。
- 固定 FFmpeg Runtime、核心源码、commit、SHA-256、构建脚本、补丁和许可证材料。
- 完成 ncmdump 官方 CLI ZIP 逐字节比对，并固定精确源码、Windows 构建工作流及静态依赖源码。
- 固定 Qt/PySide/Shiboken 精确 wheels、源码与官方许可材料并完成 wheel 文件比对。
- 更新 Manifest、Notices、证据采集器、严格验证器输入和回归测试。

## 13. 必须由项目所有者继续处理的事项

- FFmpeg：当前自构建仅限 Qonic Audio Converter Audio Runtime；未来视频功能必须使用独立受控运行时或新的独立审核构建。
- Microsoft VC Runtime：确认当前构建与分发受有效 Visual Studio 或 Build Tools 许可覆盖。
- 在所有 BLOCKER 关闭前不得发布最终合规声明或正式 Release。

## 14. 建议的后续顺序

1. 确认 Microsoft VC Runtime 分发许可覆盖。
2. Qt 模块最小化如需进行，须独立提交、体积对比和完整功能回归。
3. 未来视频功能只能采用独立受控 Video Runtime 或独立审计的新构建。

## 15. 当前最低风险依赖路线

- 继续使用已冻结的 onedir 权威工件。
- FFmpeg 使用获批的 Qonic Audio Runtime；其对应源码、许可证、锁文件、构建脚本和补丁材料已随发行证据固定。
- ncmdump 保持当前逐字节验证通过的官方 1.5.1 CLI EXE，不做替换。
- Qt 保持现有模块全集与 GPL 路线；模块最小化独立提交、体积对比和完整回归。

## 16. 本阶段修改范围

- 合规工具与测试：`Tools/compliance/`。
- 审计输出：`compliance/`、`third_party/`、`LICENSES/`。
- 工件治理：`Release/External_Test/2026-07-28_b5_final/`、历史 `Release/External_Test/2026-07-24_b4edd4d/`、`Release/Non_Authoritative/`。
- 未修改应用运行逻辑、转换器、watcher、播放器核心、ncmdump 二进制及 Qt 模块集合；仅按批准替换 FFmpeg Runtime。

## 17. 明确未执行的操作

- 已完成 ffmpeg.exe 与 ffprobe.exe 的正式替换、onedir 重建、权威归档和对应源码交付。
- 未替换 ncmdump.exe；未改为 PyInstaller onefile；未删除 Qt 模块或历史工件。
- 未发布远端 Release、tag、提交或推送。

## 18. 当前验收状态

- 权威工件、FFmpeg 对应源码与正式 Runtime：通过。
- ncmdump：官方 CLI 资产、当前 EXE、精确源码与静态依赖材料验证通过。
- Qt/PySide/Shiboken 材料：通过；最小化：按决定推迟。
- 最终结论：B5 运行时替换与可审计源码交付已验证；残留项均为 WARNING，不构成 FFmpeg 运行时 BLOCKER。

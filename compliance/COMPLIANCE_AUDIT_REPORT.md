# Qonic Audio Third-Party Compliance Audit

> 第二阶段执行结果。本文是技术证据报告，不是法律意见；存在 BLOCKER 时不得表述为“完整合规”。

## 1. 执行摘要

- 项目正式名称为 `Qonic Audio`，旧名称 `CherryQ Audio Converter` 只可出现在历史证据中。
- 唯一权威工件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z`。
- 权威归档 SHA-256：`649E38524AF2F3DCE33FCBC43AC29B7111623D033F3537DE55EF5CD45994E926`；所有者冻结值：`649E38524AF2F3DCE33FCBC43AC29B7111623D033F3537DE55EF5CD45994E926`。
- 权威工件校验：`True`；同版本候选分叉：`False`。
- 当前结论：`1` 个 BLOCKER、`4` 个 WARNING。

## 2. 当前发行结构

- 正式结构继续固定为 PyInstaller `onedir`，未引入 onefile。
- 权威归档及其对应展开目录是本报告唯一输入。
- 旧同名不同内容工件已移动到 `Release/Non_Authoritative/2026-07-24_pre_freeze/`，并以 `NOT_FOR_RELEASE.md` 标记；未删除。
- 构建中间目录不属于发布候选，不纳入权威身份判断。

## 3. 实际第三方二进制清单

- 权威展开目录含 FFmpeg、ffprobe、ncmdump、PySide6/Shiboken6、Qt DLL/QML/plugins 和 Microsoft VC Runtime。
- FFmpeg 运行路径为 `Tools/ffmpeg/bin/ffmpeg.exe`，Pitch 探测使用同目录 `ffprobe.exe`。
- ncmdump 运行路径为 `Tools/ncmdump/ncmdump.exe`，由子进程调用。
- Qt/PySide/Shiboken 已建立逐文件 SHA-256 清单；实际扫描 `2848` 个文件。

## 4. FFmpeg 调查结果

- 当前版本：`8.1.1-full_build-www.gyan.dev`；分类：`FFmpeg-GPL-CANDIDATE`。
- 保留路线：Gyan GPLv3 full build；未替换 `ffmpeg.exe` 或 `ffprobe.exe`。
- 官方资产：`ffmpeg-8.1.1-full_build.7z`；SHA-256：`5DF9759304B5714CC99FF46AF8A73D83217A51726524516FFB25501E754A5873`。
- 本地两个 EXE 与官方 Gyan 资产逐字节一致：`True`。
- FFmpeg 核心源码 commit：`239f2c733de417201d7ad3b3b8b0d9b63285b2b1`；源码 SHA-256：`EC0AA20FB9F6FD3692FFC04DC12FFA43CFFFC4A479E388CCD7910EC6CFE188A2`。
- 提供者公开确认的环境：`MSYS2 / mingw-64 environment with gcc + GNU toolchain`。
- 官方包内 README SHA-256：`35EF02F329D062A1B49397A2869718264B5F12776517791C02126F0EFD323528`；已恢复 `70` 条外部库版本记录。
- 阻断：Gyan 未公开 8.1.1 的精确脚本 revision、本地修改、补丁集和全部静态依赖对应源码；MABS 仅是提供者建议的复现候选，不能当作原构建证据。`exact_source_closed = False`。

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
- FFmpeg 按 GPL-3.0-only 路线记录；许可证、精确官方资产和核心源码已归档，提供者构建链仍阻断。
- ncmdump MIT 原文、官方 CLI 资产、精确 commit 源码和静态依赖材料已归档并校验。
- Qt/PySide/Shiboken 按 Community Edition GPL-3.0 路线记录，精确 wheels、源码和官方许可材料已闭合。
- 8 个 Microsoft VC Runtime DLL 已从 Qt wheel 比对范围中单列，许可条款已归档，仍需所有者确认分发许可覆盖。
- 补充扫描发现的 NumPy、Pillow 与 charset-normalizer 不属于本轮三组核心闭环；其许可证状态仍待独立验证，严格校验会保留 WARNING。

## 8. 已确认的事实

- 唯一发行工件、对应展开目录和 SHA-256 已冻结并通过检查。
- FFmpeg/ffprobe 与官方 Gyan 8.1.1 full build 逐字节一致。
- FFmpeg 核心源码 commit 和源码归档 SHA-256 已固定。
- 当前 ncmdump.exe 与官方 1.5.1 Windows amd64 CLI 资产逐字节一致。
- ncmdump 精确源码、Windows 构建工作流、vcpkg baseline、TagLib 2.0.2、zlib 1.3.1 与 utfcpp 4.0.6 已固定。
- Qt 精确 wheels、实际模块源码和官方许可材料已建立可复核清单。
- Qt Multimedia FFmpeg 7.1.3 attribution、版权、许可证与精确源码已建立可复核清单。

## 9. 尚未确认的事实

- Gyan 8.1.1 精确构建脚本 revision、本地修改、补丁集和全部静态依赖的对应源码。
- ncmdump 官方 GitHub Actions 的具体 runner 镜像版本与编译器补丁版本未在 Release 元数据中固定。
- Microsoft VC Runtime 的当前构建/分发是否由有效 Visual Studio 或 Build Tools 许可覆盖。
- NumPy、Pillow、charset-normalizer 的精确打包来源、必要性和最终许可证材料。
- Qt 模块真正最小集合；该事项已明确推迟到独立阶段。

## 10. 阻断问题

- `FFMPEG_BUILD_CHAIN_INCOMPLETE`：项目所有者已停止将 Gyan 作为最终方案并批准 Qonic 自构建路线。B1/B2/B3 已闭合固定 FFmpeg commit、7 组源码 SHA-256、容器/工具链/配置锁、候选二进制、Windows 能力/功能矩阵与 Corresponding Source；B4 隔离 onedir/真实媒体回归和 B5 所有者替换审批尚未完成。

## 11. 普通警告

- `FFMPEG_SELF_BUILD_ROUTE_SELECTED`：项目所有者已选择 GPL 兼容的 Qonic 自构建路线；当前 Gyan 仅作为内部测试与能力对比基线，在批准替换前保持不动。
- `QT_GPL_ONLY_MODULES_RETAINED`：发行包包含 18 组 GPL-only 模块；项目采用 GPL-3.0 路线，所有者决定本轮保留并推迟最小化。
- `QT_POSSIBLY_UNUSED_MODULES`：发行包包含 126 组 POSSIBLY_UNUSED Qt/QML/插件模块。
- `MSVC_REDISTRIBUTION_LICENSE_CONFIRMATION`：8 个 Microsoft VC Runtime DLL 已单列并归档许可条款；仍需所有者确认构建/分发受有效 Visual Studio 或 Build Tools 许可覆盖。

## 12. 本阶段已自动完成的整改

- 冻结并验证唯一权威归档与展开目录。
- 隔离同名不同内容旧工件并标记 `NOT_FOR_RELEASE`。
- 固定 FFmpeg 官方资产、核心源码、commit 和 SHA-256，完成两个 EXE 的流式逐字节比对。
- 完成 ncmdump 官方 CLI ZIP 逐字节比对，并固定精确源码、Windows 构建工作流及静态依赖源码。
- 固定 Qt/PySide/Shiboken 精确 wheels、源码与官方许可材料并完成 wheel 文件比对。
- 更新 Manifest、Notices、证据采集器、严格验证器输入和回归测试。

## 13. 必须由项目所有者继续处理的事项

- FFmpeg：Gyan 未公开构建脚本、补丁集和静态依赖锁定材料；需向提供者索取或由所有者确认继续保持阻塞。
- Microsoft VC Runtime：确认当前构建与分发受有效 Visual Studio 或 Build Tools 许可覆盖。
- 在所有 BLOCKER 关闭前不得发布最终合规声明或正式 Release。

## 14. 建议的后续顺序

1. 在具备 Docker/Podman linux/amd64 支持的环境执行固定容器构建，生成隔离候选。
2. 在 Windows 隔离 onedir 中完成候选能力、缺失 DLL、路径与真实媒体回归。
3. 确认 Microsoft VC Runtime 分发许可覆盖。
4. 仅在候选和 Corresponding Source 与最终哈希绑定后生成替换提案；所有者批准前不替换。

## 15. 当前最低风险依赖路线

- 继续使用已冻结的 onedir 权威工件。
- FFmpeg 保持当前逐字节验证通过的 Gyan GPL 构建，不擅自替换。
- ncmdump 保持当前逐字节验证通过的官方 1.5.1 CLI EXE，不做替换。
- Qt 保持现有模块全集与 GPL 路线；模块最小化独立提交、体积对比和完整回归。

## 16. 本阶段修改范围

- 合规工具与测试：`Tools/compliance/`。
- 审计输出：`compliance/`、`third_party/`、`LICENSES/`。
- 工件治理：`Release/External_Test/2026-07-24_b4edd4d/`、`Release/Non_Authoritative/`。
- 未修改应用运行逻辑、转换器、watcher、播放器核心、FFmpeg/ncmdump 二进制及 Qt 模块集合。

## 17. 明确未执行的操作

- 未替换 ffmpeg.exe、ffprobe.exe 或 ncmdump.exe。
- 未改为 PyInstaller onefile。
- 未删除 Qt DLL、QML 模块、插件或 GPL-only 候选模块。
- 未删除旧发行工件；仅移动并标记。
- 未发布 Release、tag、提交或推送远端。
- 未在存在 BLOCKER 时生成最终合规 ZIP。

## 18. 当前验收状态

- 权威工件：通过。
- FFmpeg 官方二进制对应：通过；提供者完整构建链：阻断。
- ncmdump：官方 CLI 资产、当前 EXE、精确源码与静态依赖材料验证通过。
- Qt/PySide/Shiboken 材料：通过；最小化：按决定推迟。
- 最终结论：第二阶段已完成可自动执行部分，但完整第三方依赖合规闭环尚未达成。

## 19. Qonic FFmpeg 自构建路线 B1/B2（2026-07-26）

- 已扫描代码与测试并生成命令清单、格式矩阵、功能分类和当前 Gyan 能力基线。
- 推荐固定 Debian OCI digest + 2026-07-13 Debian snapshot + MinGW-w64 win32-thread 交叉编译。
- 固定 FFmpeg 8.1.1 commit、zlib、LAME、libogg、libvorbis、Opus、Rubber Band 4.0.0 共 7 份源码；下载/缓存文件全部通过 SHA-256。
- 配置采用 `--disable-everything` 白名单、`--enable-gpl --enable-version3`，明确 `--disable-nonfree --disable-network --disable-autodetect`。
- 静态构建测试 `23 passed`，合规与构建测试合计 `44 passed`。
- 已在 Docker Desktop `linux/amd64` 完成 B3 完整重构建，候选 Windows 功能矩阵 `21/21 passed`，最终完整重跑哈希一致；未修改正式工具或发行工件。

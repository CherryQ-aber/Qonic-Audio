# Owner Decisions

项目：`Qonic Audio` / `Qonic Audio Converter & Editor`

状态：以下五项路线均已由项目所有者确认，不重新打开。

## 已批准决定

1. 唯一权威发行工件为 `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test.7z` 及其对应展开目录；其他同版本差异工件仅隔离并标记 `NOT_FOR_RELEASE`。
2. 正式发行暂时保留 FFmpeg 8.1.1 gyan.dev GPL 构建；最终路线改为 Qonic 自构建，B4 回归和 B5 所有者审批前不得替换 ffmpeg.exe 或 ffprobe.exe。
3. ncmdump 先逐字节比对；若不一致或资产类型错误立即停止，未经批准不得替换。
4. PyInstaller `onedir` 是唯一正式结构，本轮不维护 onefile。
5. 本轮保留 Qt `POSSIBLY_UNUSED` 与 GPL-only 候选模块；模块最小化作为后续独立阶段。

## 当前执行结果

- 权威工件验证通过，旧差异工件已隔离且未删除。
- FFmpeg/ffprobe 与官方 Gyan 8.1.1 full build 逐字节一致；核心 FFmpeg 源码已固定。
- Qonic 自构建 B3 已在 Docker Desktop `linux/amd64` 完成，固定候选、DLL/能力证据、Windows `21/21` 功能矩阵和 Corresponding Source 已生成；正式二进制未替换。
- ncmdump 官方 CLI ZIP 与权威发行目录 EXE 逐字节一致；保留当前 EXE，未解压覆盖或替换。
- ncmdump 精确 commit 源码、Windows 构建工作流、vcpkg baseline 与静态依赖源码已固定并校验。
- PySide6/Shiboken6 精确 wheels、实际 Qt 模块源码和官方许可材料已闭合。

## 仍需项目所有者或上游处理

- FFmpeg：完成 B4 隔离 onedir/真实媒体回归后生成 B5 替换提案，等待所有者明确批准；不得自动替换正式二进制。
- Microsoft VC Runtime：确认当前构建与分发受有效 Visual Studio 或 Build Tools 许可覆盖。
- 在所有 BLOCKER 关闭前不得发布最终合规声明或正式 Release。

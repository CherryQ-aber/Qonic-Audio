# Owner Decisions

项目：`Qonic Audio` / `Qonic Audio Converter & Editor`

状态：`FORMAL_REPLACEMENT_VERIFIED`。B5 仅闭合 Qonic Audio Converter 的 Audio Runtime；它不是未来所有 Qonic 项目的通用 FFmpeg 承诺。

## 已批准并执行的决定

1. 唯一权威发行工件为 B5 的 `Qonic_Audio_v5.0_internal_test.7z` 及其对应 onedir 展开目录；此前工件仅作历史或回滚证据。
2. 已按批准将 FFmpeg/ffprobe 替换为 Qonic 自构建 Audio Runtime，并通过候选 SHA-256、对应源码、onedir、归档、smoke 和完整回归验证。
3. 对应源码包固定 FFmpeg、Rubber Band、全部静态依赖源码、构建脚本、补丁、configure 参数、许可证与版权材料，并提供重建说明。
4. ncmdump 保持当前逐字节验证通过的官方 1.5.1 CLI EXE，不做替换。
5. PyInstaller `onedir` 是唯一正式结构；Qt 模块最小化仍为独立后续阶段。

## Runtime Contract

- 当前 Runtime 仅为 `Qonic Audio Converter Audio Runtime`。
- 未来视频能力必须使用独立受控的 FFmpeg Video Runtime，或在正式集成时重新生成并独立审计新的构建。
- 不因未来可能的视频功能保留不可审计的超大全功能 Gyan 构建，也不将当前候选描述为永久通用 Runtime。

## 剩余人工事项

- {item}
- {item}

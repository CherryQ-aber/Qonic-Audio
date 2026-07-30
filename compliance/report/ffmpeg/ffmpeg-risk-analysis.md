# FFmpeg Risk Analysis

- 事实：正式运行时与获批 Qonic 候选二进制 SHA-256 一致。
- 事实：构建使用 GPL/version3，`--enable-nonfree` 未启用。
- 事实：Corresponding Source 包含 FFmpeg、Rubber Band、全部静态依赖源码、锁文件、配置、脚本、补丁目录、测试和许可证材料。
- 事实：B5 最终 onedir、归档、三个 packaged QML smoke 和完整回归已验证。
- 边界：该二进制仅是 Qonic Audio Converter Audio Runtime；未来视频功能必须使用独立受控运行时或重新生成并审核的新构建。

# ncmdump Risk Analysis

- 事实：自报版本为 `1.5.1`。
- 事实：项目通过 `subprocess` 调用独立 `ncmdump.exe`，未发现 ncmdump DLL 调用路径。
- 推断：TagLib 链接状态为 `STATIC_LINK_CANDIDATE`；依据有限，不能当作构建事实。
- 构建证据：`GitHub Actions windows-latest; CMake Release; VCPKG_TARGET_TRIPLET=x64-windows-static`。
- 精确源码：commit `76a55d862f767ee20ae417ecd128fde442eea77f`，SHA-256 `70D1C692130B0C0C53276417FD6246C02C4C39D057005F0435FF4942C7CFF11E`，verified=`True`。
- 静态依赖材料：vcpkg baseline `a62ce77d56ee07513b4b67de1ec2daeaebfae51a`，closed=`True`。
- 已闭合：本地 ncmdump.exe 与官方 CLI 资产逐字节一致。

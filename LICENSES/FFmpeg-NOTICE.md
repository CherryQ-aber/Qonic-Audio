# FFmpeg Notice

当前项目发行包会随包携带：

- `Tools/ffmpeg/bin/ffmpeg.exe`
- `Tools/ffmpeg/bin/ffprobe.exe`

本仓库当前仅在 `Tools/ffmpeg/` 保存运行所需二进制文件。当前 GPLv3 全文由发行包顶层 `LICENSE` 提供。

当前候选二进制的可核验信息：

- 自报版本：`ffmpeg 8.1.1-full_build-www.gyan.dev`
- SHA-256：`09948D4CDD0650DA6FF5A87577469F2A218DC2615AE379F8F734D24C49DE0F73`
- `ffprobe.exe` SHA-256：`A6618E99BB58869DED3C6F37B53AA1A8D701C3591DBB7B5B317D47369C112BE2`
- 官方资产：`ffmpeg-8.1.1-full_build.7z`
- 官方资产 SHA-256：`5DF9759304B5714CC99FF46AF8A73D83217A51726524516FFB25501E754A5873`
- 本地 `ffmpeg.exe` 与 `ffprobe.exe` 均已与该官方资产逐字节验证一致
- FFmpeg 核心源码 commit：`239f2c733de417201d7ad3b3b8b0d9b63285b2b1`
- 本地源码归档 SHA-256：`EC0AA20FB9F6FD3692FFC04DC12FFA43CFFFC4A479E388CCD7910EC6CFE188A2`
- 构建配置包含：`--enable-gpl --enable-version3 --enable-static`
- 提供者公开确认环境：MSYS2 / mingw-64、GCC 与 GNU toolchain
- 官方包内 `README.txt` SHA-256：`35EF02F329D062A1B49397A2869718264B5F12776517791C02126F0EFD323528`
- 包内 README 已恢复 70 条外部库版本记录；该记录不等同于完整依赖源码和源码哈希
- 二进制提供方页面：`https://www.gyan.dev/ffmpeg/builds/`
- FFmpeg 官方许可说明：`https://ffmpeg.org/legal.html`

审核结论：

- 当前 v5.0 内部测试候选已明确标记 FFmpeg 为随包外部工具。
- 本轮按项目所有者决定保留该 GPLv3 构建，不替换二进制。
- 官方资产、FFmpeg 核心源码、完整 `-buildconf` 和包内依赖版本表已闭合。
- Gyan 公开说明使用 MSYS2 / mingw-64、GCC 与 GNU toolchain，并曾建议使用 media-autobuild_suite 复现；但没有说明 8.1.1 对应的精确脚本 revision、本地修改或补丁集。
- 由于全部静态依赖的对应源码归档与源码哈希仍未随资产发布，完整构建链继续保持 BLOCKER。

建议至少核对：

- Gyan 8.1.1 精确构建脚本 revision、本地修改与补丁集
- 全部静态依赖的对应源码归档、源码哈希与许可证材料

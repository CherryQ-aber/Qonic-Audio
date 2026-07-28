# FFmpeg Risk Analysis

- 事实：技术分类为 `FFmpeg-GPL-CANDIDATE`。
- 事实：构建提供者线索为 `gyan.dev`。
- 事实：`--enable-gpl` = `True`。
- 事实：`--enable-version3` = `True`。
- 事实：`--enable-nonfree` = `False`。
- 推断：当前静态 full build 应按 GPLv3 候选路线继续审核；这不是法律结论。
- 事实：官方 Gyan 资产与发行 ffmpeg/ffprobe 逐字节一致 = `True`。
- 事实：FFmpeg commit 源码归档及 SHA-256 已闭合 = `True`。
- 事实：包内 README 已恢复 `70` 条外部库版本记录。
- 事实：提供者公开确认的环境为 `MSYS2 / mingw-64 environment with gcc + GNU toolchain`。
- 事实：提供者曾指向 media-autobuild_suite 作为复现候选，但没有声明 8.1.1 使用的精确脚本 revision。
- 事实：项目所有者已决定保留当前 Gyan GPL 构建，禁止未经再次批准替换二进制。
- 阻塞：精确构建脚本 revision、本地修改、补丁集及全部静态依赖对应源码仍未发布；不能将完整构建链标记为已闭合。
- 建议：向构建提供者索取 8.1.1 对应脚本快照、补丁和依赖源码包；MABS 只能作为复现候选，不能冒充原构建证据。

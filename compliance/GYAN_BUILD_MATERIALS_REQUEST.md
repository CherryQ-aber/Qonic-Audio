# Gyan FFmpeg 8.1.1 Build Materials Request

本文件是待项目所有者人工发送的材料请求草稿；尚未向 Gyan 发邮件或创建 GitHub Issue。

## Target

- Release: `8.1.1`
- Asset: `ffmpeg-8.1.1-full_build.7z`
- Asset SHA-256: `5DF9759304B5714CC99FF46AF8A73D83217A51726524516FFB25501E754A5873`
- FFmpeg source commit: `239f2c733de417201d7ad3b3b8b0d9b63285b2b1`

## Request

Hello,

We distribute the unmodified `ffmpeg.exe` and `ffprobe.exe` from the Gyan
FFmpeg 8.1.1 full static build as separate subprocess tools in an open-source
Windows desktop application.

For reproducible provenance and GPL corresponding-source records, could you
please provide or identify the exact materials used to create this asset?

1. The exact build-script repository and commit/revision.
2. Any local changes, configuration files, or patches applied to those scripts.
3. The MSYS2 environment, MinGW/GCC toolchain snapshot, and package manifest.
4. The complete dependency lock or source list for statically linked libraries.
5. Source archive URLs and hashes for dependencies built from rolling git
   revisions.
6. Any patches applied to FFmpeg or its dependencies.

The package `README.txt` and `ffmpeg -buildconf` already give us the FFmpeg
commit, configuration, and many dependency versions. We specifically need the
remaining script, patch, and corresponding-source identity needed to reproduce
the distributed object code.

If the build used `media-autobuild_suite`, please identify the exact suite
commit and any modified configuration or local patches used for the 8.1.1
asset.

Thank you.

## Suggested channels

- Email address listed on the official builds page: `builds` at the Gyan
  domain.
- GyanD/codexffmpeg GitHub Issues.

发送属于外部操作，必须由项目所有者明确批准后执行。

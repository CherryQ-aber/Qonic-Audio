# Third-Party Notices

Product: `Qonic Audio`
Version: `5.0 Internal Test`

本文件由本地合规工具依据所有者冻结的唯一权威发行工件生成。
Manifest 中仍有 BLOCKER；本文件是当前证据清单，不构成“完整合规”声明。

## FFmpeg

- 组件类别：external-binary
- 实际版本：8.1.1-full_build-www.gyan.dev
- 上游项目：https://github.com/FFmpeg/FFmpeg
- 上游发行/资产：8.1.1 / ffmpeg-8.1.1-full_build.7z
- 上游资产 SHA-256：5DF9759304B5714CC99FF46AF8A73D83217A51726524516FFB25501E754A5873
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ffmpeg/bin/ffmpeg.exe`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ffmpeg/bin/ffprobe.exe`
- 上游声明许可证：GPLv3 candidate
- 本项目采用路线：GPL-3.0-only
- 版权所有者/声明：Copyright (c) 2000-2026 the FFmpeg developers; individual component notices remain in the corresponding source.
- 是否修改：false
- 使用方式：subprocess
- 对应源码获取位置：https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/239f2c733de417201d7ad3b3b8b0d9b63285b2b1
- 对应源码 SHA-256：EC0AA20FB9F6FD3692FFC04DC12FFA43CFFFC4A479E388CCD7910EC6CFE188A2
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-GPL-3.0-BUILD
- 尚未解决的问题：
  - Gyan 未公开生成 8.1.1 资产所用的精确脚本 revision、本地修改和补丁集
  - 包内 README 可恢复部分依赖版本，但未随资产发布全部静态依赖的对应源码归档与源码哈希
  - 部分依赖使用 rolling git 描述或 latest 标记，无法仅凭 README 固定完整源码身份

## ncmdump

- 组件类别：external-binary
- 实际版本：1.5.1
- 上游项目：https://github.com/taurusxin/ncmdump
- 上游发行/资产：1.5.1 / ncmdump-1.5.1-windows-amd64.zip
- 上游资产 SHA-256：BB849221C06B8FDBFF42AEFB86BAEA9C07256568658D80F4BE72A39A2A1632DC
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ncmdump/ncmdump.exe`
- 上游声明许可证：MIT
- 本项目采用路线：MIT
- 版权所有者/声明：Upstream LICENSE.txt retains '[year] [fullname]' placeholders; Qonic Audio does not invent or replace the missing holder text.
- 是否修改：false
- 使用方式：subprocess
- 对应源码获取位置：https://codeload.github.com/taurusxin/ncmdump/tar.gz/76a55d862f767ee20ae417ecd128fde442eea77f
- 对应源码 SHA-256：70D1C692130B0C0C53276417FD6246C02C4C39D057005F0435FF4942C7CFF11E
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-UPSTREAM-ASSET-SOURCE-AND-LICENSE
- 尚未解决的问题：
  - 官方 GitHub Actions 的具体 runner 镜像版本与编译器补丁版本未在 Release 元数据中固定

## TagLib

- 组件类别：ncmdump-statically-linked-dependency
- 实际版本：2.0.2
- 上游项目：https://github.com/taglib/taglib
- 上游发行/资产：2.0.2 / taglib-2.0.2.tar.gz
- 上游资产 SHA-256：0DE288D7FE34BA133199FD8512F19CC1100196826EAFCB67A33B224EC3A59737
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ncmdump/ncmdump.exe`
- 上游声明许可证：LGPL-2.1-only OR MPL-1.1
- 本项目采用路线：MPL-1.1
- 版权所有者/声明：见精确上游源码归档中的许可证与版权声明。
- 是否修改：false
- 使用方式：statically linked into ncmdump.exe
- 对应源码获取位置：https://codeload.github.com/taglib/taglib/tar.gz/refs/tags/v2.0.2
- 对应源码 SHA-256：0DE288D7FE34BA133199FD8512F19CC1100196826EAFCB67A33B224EC3A59737
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-EXACT-SOURCE-ARCHIVE
- 尚未解决的问题：

## zlib

- 组件类别：ncmdump-statically-linked-dependency
- 实际版本：1.3.1
- 上游项目：https://github.com/madler/zlib
- 上游发行/资产：1.3.1 / zlib-1.3.1.tar.gz
- 上游资产 SHA-256：17E88863F3600672AB49182F217281B6FC4D3C762BDE361935E436A95214D05C
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ncmdump/ncmdump.exe`
- 上游声明许可证：Zlib
- 本项目采用路线：Zlib
- 版权所有者/声明：见精确上游源码归档中的许可证与版权声明。
- 是否修改：false
- 使用方式：statically linked into ncmdump.exe
- 对应源码获取位置：https://codeload.github.com/madler/zlib/tar.gz/refs/tags/v1.3.1
- 对应源码 SHA-256：17E88863F3600672AB49182F217281B6FC4D3C762BDE361935E436A95214D05C
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-EXACT-SOURCE-ARCHIVE
- 尚未解决的问题：

## utfcpp

- 组件类别：ncmdump-statically-linked-dependency
- 实际版本：4.0.6
- 上游项目：https://github.com/nemtrif/utfcpp
- 上游发行/资产：4.0.6 / utfcpp-4.0.6.tar.gz
- 上游资产 SHA-256：6920A6A5D6A04B9A89B2A89AF7132F8ACEFD46E0C2A7B190350539E9213816C0
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/Tools/ncmdump/ncmdump.exe`
- 上游声明许可证：BSL-1.0
- 本项目采用路线：BSL-1.0
- 版权所有者/声明：见精确上游源码归档中的许可证与版权声明。
- 是否修改：false
- 使用方式：statically linked into ncmdump.exe
- 对应源码获取位置：https://codeload.github.com/nemtrif/utfcpp/tar.gz/refs/tags/v4.0.6
- 对应源码 SHA-256：6920A6A5D6A04B9A89B2A89AF7132F8ACEFD46E0C2A7B190350539E9213816C0
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-EXACT-SOURCE-ARCHIVE
- 尚未解决的问题：

## PySide6 / Qt 6 / shiboken6

- 组件类别：gui-runtime
- 实际版本：6.11.1
- 上游项目：https://code.qt.io/cgit/pyside/pyside-setup.git/
- 上游发行/资产：6.11.1 / `pyside6-6.11.1-cp310-abi3-win_amd64.whl`, `pyside6_essentials-6.11.1-cp310-abi3-win_amd64.whl`, `pyside6_addons-6.11.1-cp310-abi3-win_amd64.whl`, `shiboken6-6.11.1-cp310-abi3-win_amd64.whl`
- 上游资产 SHA-256：`pyside6-6.11.1-cp310-abi3-win_amd64.whl`=`0968877AB1FB4EF3587A284DA6FE05E8647ADA56A6A3750B6395188E01F4ABA6`, `pyside6_essentials-6.11.1-cp310-abi3-win_amd64.whl`=`63311BD48E32C584599AB04B9EF7C324082374CD2C9FA533F978FB893BB47E40`, `pyside6_addons-6.11.1-cp310-abi3-win_amd64.whl`=`0D13C4DFD671B050A48E4F8D8DDC724B7248F9C0437E7FC47FDF316278572923`, `shiboken6-6.11.1-cp310-abi3-win_amd64.whl`=`C2C6863AA80EC18C0F82CEA3417837B279CDC60024AC17123461DC9042577DF7`
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/opengl32sw.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/generic/qtuiotouchplugin.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/iconengines/qsvgicon.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qgif.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qicns.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qico.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qjpeg.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qpdf.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qsvg.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qtga.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qtiff.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/plugins/imageformats/qwbmp.dll`；另有 2823 项见 Manifest
- 上游声明许可证：LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- 本项目采用路线：GPL-3.0-only
- 版权所有者/声明：The Qt Company Ltd. and other Qt/PySide contributors; module-specific notices are preserved in the archived source and official third-party-code documents.
- 是否修改：false
- 使用方式：Python binding plus dynamically loaded Qt DLL/QML/plugins
- 对应源码获取位置：https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/pyside-setup-everywhere-src-6.11.1.tar.xz
- 对应源码 SHA-256：6FFD9835BB0DD2C56F061D62F1616BB1707CFC0202B80E3165D6BE087F3965E2
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-GPL-3.0-ROUTE
- 尚未解决的问题：
  - POSSIBLY_UNUSED 与 GPL-only 候选模块按所有者决定保留；最小化留待独立阶段

## Qt Multimedia FFmpeg

- 组件类别：gui-runtime-third-party
- 实际版本：7.1.3
- 上游项目：https://github.com/FFmpeg/FFmpeg
- 上游发行/资产：n7.1.3 / `pyside6_addons-6.11.1-cp310-abi3-win_amd64.whl`
- 上游资产 SHA-256：`pyside6_addons-6.11.1-cp310-abi3-win_amd64.whl`=`0D13C4DFD671B050A48E4F8D8DDC724B7248F9C0437E7FC47FDF316278572923`
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/avcodec-61.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/avformat-61.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/avutil-59.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/swresample-5.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/swscale-8.dll`
- 上游声明许可证：LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND BSD-Source-Code AND ISC AND MIT AND MPL-2.0
- 本项目采用路线：LGPL-2.1-or-later
- 版权所有者/声明：Copyright (c) 2000-2023 the FFmpeg developers
- 是否修改：false
- 使用方式：Qt Multimedia FFmpeg backend dynamic libraries
- 对应源码获取位置：https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/f46e514491172d15bd74b4abb1814cd2f05a763e
- 对应源码 SHA-256：1FA39B5A6AE9AC02C2CF280EC5CC8321A0DD0B9AB34B6C73133CAFCCAF5DFA79
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：VERIFIED-QT-ATTRIBUTION-LGPL-ROUTE
- 尚未解决的问题：
  - Qt attribution 指向的预构建 FFmpeg 构建脚本仓库尚未固定到独立 commit；本轮已闭合精确 wheel、attribution、许可证和 FFmpeg 7.1.3 源码。

## Microsoft Visual C++ v14 Runtime

- 组件类别：system-runtime
- 实际版本：14.44.35211.0
- 上游项目：https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
- 上游发行/资产：v14 / 14.44.35211.0 / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/MSVCP140.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/MSVCP140_1.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/MSVCP140_2.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/VCRUNTIME140.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PySide6/VCRUNTIME140_1.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/shiboken6/MSVCP140.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/shiboken6/VCRUNTIME140.dll`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/shiboken6/VCRUNTIME140_1.dll`
- 上游声明许可证：Microsoft Software License Terms
- 本项目采用路线：Microsoft Visual C++ v14 Redistributable terms
- 版权所有者/声明：Copyright Microsoft Corporation.
- 是否修改：UNKNOWN
- 使用方式：application-local dynamic runtime
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：PROPRIETARY-REDISTRIBUTABLE-TERMS-RECORDED
- 尚未解决的问题：
  - Confirm that the build/distribution is covered by a valid Visual Studio or Build Tools license and that bundled files are unmodified redistributable runtime files.

## mutagen

- 组件类别：python-runtime
- 实际版本：1.47.0
- 上游项目：UNKNOWN
- 上游发行/资产：UNKNOWN / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`DIST/mutagen-gpl-2.0.txt`
- 上游声明许可证：GPL-2.0-or-later
- 本项目采用路线：UNKNOWN
- 版权所有者/声明：见对应上游许可证与源码包
- 是否修改：false
- 使用方式：python-import
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：DECLARED-PENDING-FILE-CHECK
- 尚未解决的问题：
  - 确认发行包内实际打包版本与本机构建环境版本一致
  - 确认许可证全文和版权声明已纳入最终合规包

## PyInstaller

- 组件类别：python-build-tool
- 实际版本：6.20.0
- 上游项目：UNKNOWN
- 上游发行/资产：UNKNOWN / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`DIST/pyinstaller-gpl-2.0-with-bootloader-exception.txt`
- 上游声明许可证：GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones)
- 本项目采用路线：UNKNOWN
- 版权所有者/声明：见对应上游许可证与源码包
- 是否修改：false
- 使用方式：build-time
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：DECLARED-PENDING-FILE-CHECK
- 尚未解决的问题：
  - 确认发行包内实际打包版本与本机构建环境版本一致
  - 确认许可证全文和版权声明已纳入最终合规包

## watchdog

- 组件类别：python-runtime
- 实际版本：6.0.0
- 上游项目：UNKNOWN
- 上游发行/资产：UNKNOWN / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`DIST/watchdog-apache-2.0.txt`
- 上游声明许可证：Apache-2.0
- 本项目采用路线：UNKNOWN
- 版权所有者/声明：见对应上游许可证与源码包
- 是否修改：false
- 使用方式：python-import
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：DECLARED-PENDING-FILE-CHECK
- 尚未解决的问题：
  - 确认发行包内实际打包版本与本机构建环境版本一致
  - 确认许可证全文和版权声明已纳入最终合规包

## NumPy

- 组件类别：python-runtime-transitive
- 实际版本：2.4.6
- 上游项目：UNKNOWN
- 上游发行/资产：UNKNOWN / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/numpy`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/numpy-2.4.6.dist-info`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/numpy.libs`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/numpy-2.4.6.dist-info/licenses/numpy`, `Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/numpy-2.4.6.dist-info/licenses/numpy/_core/include/numpy`
- 上游声明许可证：BSD-3-Clause candidate
- 本项目采用路线：UNKNOWN
- 版权所有者/声明：见对应上游许可证与源码包
- 是否修改：false
- 使用方式：python-import-or-transitive-bundle
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：License status pending verification
- 尚未解决的问题：
  - 确认该组件是否为当前功能直接依赖或 PyInstaller 环境污染带入
  - 确认完整许可证与第三方声明

## Pillow

- 组件类别：python-runtime-transitive
- 实际版本：12.2.0
- 上游项目：UNKNOWN
- 上游发行/资产：UNKNOWN / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/PIL`
- 上游声明许可证：HPND candidate
- 本项目采用路线：UNKNOWN
- 版权所有者/声明：见对应上游许可证与源码包
- 是否修改：false
- 使用方式：python-import-or-transitive-bundle
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：License status pending verification
- 尚未解决的问题：
  - 确认该组件是否为当前功能直接依赖或 PyInstaller 环境污染带入
  - 确认完整许可证与第三方声明

## charset-normalizer

- 组件类别：python-runtime-transitive
- 实际版本：3.4.7
- 上游项目：UNKNOWN
- 上游发行/资产：UNKNOWN / UNKNOWN
- 上游资产 SHA-256：UNKNOWN
- 实际分发文件：`Release/External_Test/2026-07-24_b4edd4d/Qonic_Audio_v5.0_internal_test/_internal/charset_normalizer`
- 上游声明许可证：MIT candidate
- 本项目采用路线：UNKNOWN
- 版权所有者/声明：见对应上游许可证与源码包
- 是否修改：false
- 使用方式：python-import-or-transitive-bundle
- 对应源码获取位置：UNKNOWN
- 对应源码 SHA-256：UNKNOWN
- 本地 Manifest 路径：`third_party/THIRD_PARTY_MANIFEST.json`
- 许可证状态：License status pending verification
- 尚未解决的问题：
  - 确认该组件是否为当前功能直接依赖或 PyInstaller 环境污染带入
  - 确认完整许可证与第三方声明

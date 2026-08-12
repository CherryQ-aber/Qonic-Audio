# Third-Party Notices

This notice index names only the components actually found in the Qonic Audio v5.0 authoritative onedir release. Full licence bodies are in `docs/compliance/staging/licenses/`.

## CPython Runtime

- Component: CPython Runtime
- Version: 3.12.1
- Copyright / attribution: Python Software Foundation / CPython
- License: PSF-2.0
- License file location: `docs/compliance/staging/licenses/Python/LICENSE.txt`
- Upstream project: Python Software Foundation / CPython
- Source availability: https://www.python.org/downloads/release/python-3121/
- Notes: None.

## OpenSSL

- Component: OpenSSL
- Version: 3.0.11
- Copyright / attribution: The OpenSSL Project
- License: Apache-2.0
- License file location: `docs/compliance/staging/licenses/OpenSSL/Apache-2.0.txt`
- Upstream project: The OpenSSL Project
- Source availability: https://github.com/openssl/openssl/tree/openssl-3.0.11
- Notes: None.

## libffi

- Component: libffi
- Version: ABI 8 (source version not embedded)
- Copyright / attribution: libffi
- License: MIT
- License file location: `docs/compliance/staging/licenses/libffi/MIT.txt`
- Upstream project: libffi
- Source availability: https://github.com/libffi/libffi
- Notes: The ABI is identified as 8, but the exact libffi source-release version is not embedded in the frozen DLL.

## NumPy

- Component: NumPy
- Version: 2.4.6
- Copyright / attribution: NumPy Developers
- License: BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0
- License file location: `docs/compliance/staging/licenses/NumPy/LICENSE.txt`, `docs/compliance/staging/licenses/NumPy/numpy/_core/include/numpy/libdivide/LICENSE.txt`, `docs/compliance/staging/licenses/NumPy/numpy/_core/src/common/pythoncapi-compat/COPYING`, `docs/compliance/staging/licenses/NumPy/numpy/_core/src/highway/LICENSE`, `docs/compliance/staging/licenses/NumPy/numpy/_core/src/multiarray/dragon4_LICENSE.txt`, `docs/compliance/staging/licenses/NumPy/numpy/_core/src/npysort/x86-simd-sort/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/_core/src/umath/svml/LICENSE`, `docs/compliance/staging/licenses/NumPy/numpy/fft/pocketfft/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/linalg/lapack_lite/LICENSE.txt`, `docs/compliance/staging/licenses/NumPy/numpy/ma/LICENSE`, `docs/compliance/staging/licenses/NumPy/numpy/random/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/random/src/distributions/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/random/src/mt19937/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/random/src/pcg64/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/random/src/philox/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/random/src/sfc64/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/numpy/random/src/splitmix64/LICENSE.md`, `docs/compliance/staging/licenses/NumPy/LICENSE.txt`, `docs/compliance/staging/licenses/NumPy/LICENSE`
- Upstream project: NumPy Developers
- Source availability: https://github.com/numpy/numpy/tree/v2.4.6
- Notes: None.

## Pillow

- Component: Pillow
- Version: 12.2.0
- Copyright / attribution: Python Pillow
- License: MIT-CMU
- License file location: `docs/compliance/staging/licenses/Pillow/LICENSE`
- Upstream project: Python Pillow
- Source availability: https://github.com/python-pillow/Pillow/tree/12.2.0
- Notes: No separately shipped Pillow codec DLL was found; the exact wheel licence material is staged.

## charset-normalizer

- Component: charset-normalizer
- Version: 3.4.7
- Copyright / attribution: charset-normalizer contributors
- License: MIT
- License file location: `docs/compliance/staging/licenses/charset_normalizer/LICENSE`
- Upstream project: charset-normalizer contributors
- Source availability: https://github.com/jawah/charset_normalizer/tree/3.4.7
- Notes: None.

## Mutagen

- Component: Mutagen
- Version: 1.47.0
- Copyright / attribution: Mutagen / Quod Libet contributors
- License: GPL-2.0-or-later
- License file location: `docs/compliance/staging/licenses/Mutagen/COPYING`
- Upstream project: Mutagen / Quod Libet contributors
- Source availability: docs/compliance/staging/artifacts/sources/mutagen-1.47.0.tar.gz
- Notes: None.

## watchdog

- Component: watchdog
- Version: 6.0.0
- Copyright / attribution: watchdog contributors
- License: Apache-2.0
- License file location: `docs/compliance/staging/licenses/watchdog/AUTHORS`, `docs/compliance/staging/licenses/watchdog/COPYING`, `docs/compliance/staging/licenses/watchdog/LICENSE`
- Upstream project: watchdog contributors
- Source availability: https://github.com/gorakhargosh/watchdog/tree/v6.0.0
- Notes: None.

## PyInstaller bootloader

- Component: PyInstaller bootloader
- Version: not embedded in frozen artifact
- Copyright / attribution: PyInstaller Development Team
- License: GPL-2.0-or-later WITH PyInstaller bootloader exception
- License file location: `docs/compliance/staging/licenses/PyInstaller/GPL-2.0-with-Bootloader-Exception.txt`
- Upstream project: PyInstaller Development Team
- Source availability: https://github.com/pyinstaller/pyinstaller
- Notes: The frozen executable's CArchive identifies the PyInstaller bootloader. The current build executable differs, so its version is not used as frozen-artifact proof; the exact build-time PyInstaller version is not embedded.

## PySide6

- Component: PySide6
- Version: 6.11.1
- Copyright / attribution: Qt for Python / The Qt Company
- License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- License file location: `docs/compliance/staging/licenses/PySide6/GPL-3.0.txt`, `docs/compliance/staging/licenses/PySide6/LGPL-3.0.txt`, `docs/compliance/staging/licenses/PySide6/LicenseRef-Qt-Commercial.txt`, `docs/compliance/staging/licenses/PySide6/SOURCE_AVAILABILITY.md`
- Upstream project: Qt for Python / The Qt Company
- Source availability: docs/compliance/QT_SOURCE_AVAILABILITY.md
- Notes: LGPL route technical staging completed. The r2 LGPL integration candidate has passed automatic and owner-confirmed visible Windows acceptance; the frozen package remains an unchanged historical GPL baseline.

## shiboken6

- Component: shiboken6
- Version: 6.11.1
- Copyright / attribution: Qt for Python / The Qt Company
- License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- License file location: `docs/compliance/staging/licenses/Shiboken6/GPL-3.0.txt`, `docs/compliance/staging/licenses/Shiboken6/LGPL-3.0.txt`, `docs/compliance/staging/licenses/Shiboken6/SOURCE_AVAILABILITY.md`
- Upstream project: Qt for Python / The Qt Company
- Source availability: docs/compliance/QT_SOURCE_AVAILABILITY.md
- Notes: LGPL route technical staging completed. The r2 LGPL integration candidate has passed automatic and owner-confirmed visible Windows acceptance; the frozen package remains an unchanged historical GPL baseline.

## Qt Runtime

- Component: Qt Runtime
- Version: 6.11.1
- Copyright / attribution: The Qt Company
- License: LGPL-3.0-only OR GPL-3.0-only, module-dependent
- License file location: `docs/compliance/staging/licenses/Qt/LGPL-2.1.txt`, `docs/compliance/staging/licenses/Qt/LGPL-3.0.txt`, `docs/compliance/staging/licenses/Qt/Qt-6.11-Licensing.html`, `docs/compliance/staging/licenses/Qt/Qt-6.11-SBOM-Documentation.html`, `docs/compliance/staging/licenses/Qt/Qt-6.11.1-Third-Party-Code.html`, `docs/compliance/staging/licenses/Qt/Qt-6.11.1-WebEngine-Licensing.html`, `docs/compliance/staging/licenses/Qt/SOURCE_AVAILABILITY.md`
- Upstream project: The Qt Company
- Source availability: docs/compliance/QT_SOURCE_AVAILABILITY.md
- Notes: The r2 candidate removes the verified GPL-only groups. The r2 LGPL integration candidate has passed automatic and owner-confirmed visible Windows acceptance; the frozen package remains an unchanged historical GPL baseline.

## Qt Multimedia FFmpeg

- Component: Qt Multimedia FFmpeg
- Version: 7.1.3
- Copyright / attribution: FFmpeg developers / Qt Multimedia
- License: LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND BSD-Source-Code AND ISC AND MIT AND MPL-2.0
- License file location: `docs/compliance/staging/licenses/Qt_Multimedia_FFmpeg/LGPL-2.1.txt`
- Upstream project: FFmpeg developers / Qt Multimedia
- Source availability: third_party/source-archives/qt/ffmpeg-f46e514491172d15bd74b4abb1814cd2f05a763e.tar.gz
- Notes: None.

## FFmpeg Audio Runtime

- Component: FFmpeg Audio Runtime
- Version: 8.1.1
- Copyright / attribution: FFmpeg developers and listed static dependencies
- License: GPL-3.0-or-later
- License file location: `docs/compliance/staging/licenses/FFmpeg/GPL-3.0.txt`
- Upstream project: FFmpeg developers and listed static dependencies
- Source availability: Corresponding_Source/qonic-ffmpeg-complete-corresponding-source.tar.gz
- Notes: Binary hashes, configuration and corresponding-source bundle match the closed B5 evidence.

## ncmdump

- Component: ncmdump
- Version: 1.5.1
- Copyright / attribution: ncmdump contributors
- License: MIT
- License file location: `docs/compliance/staging/licenses/ncmdump/MIT.txt`
- Upstream project: ncmdump contributors
- Source availability: third_party/source-archives/ncmdump/ncmdump-76a55d862f767ee20ae417ecd128fde442eea77f.tar.gz
- Notes: None.

## Microsoft VC Runtime

- Component: Microsoft VC Runtime
- Version: 14.x (11 reviewed files)
- Copyright / attribution: Microsoft
- License: Microsoft Visual Studio 2026 REDIST terms
- License file location: `docs/compliance/staging/licenses/Microsoft/REDIST-DISPOSITION.md`
- Upstream project: Microsoft
- Source availability: https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution
- Notes: None.

## Inno Setup

- Component: Inno Setup installer engine and Simplified Chinese messages
- Version: 6.7.3 / language file compatible with 6.5.0+
- Copyright / attribution: Copyright (C) 1997-2026 Jordan Russell; portions Copyright (C) 2000-2026 Martijn Laan; Simplified Chinese translation maintained by Zhenghan Yang
- License: Inno Setup License
- License file location: `LICENSES/Inno-Setup-License.txt`
- Upstream project: Jordan Russell's Software / Inno Setup
- Source availability: https://github.com/jrsoftware/issrc/tree/is-6_7_3
- Notes: Build/installer component only; the application runtime architecture and application licence are unchanged.

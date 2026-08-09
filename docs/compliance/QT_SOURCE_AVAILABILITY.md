# Qt 6.11.1 / Qt for Python 6.11.1 Source Availability

This record is for the Qonic Audio v5.0 authoritative package only.  It gives
recipients a version-specific route to the source corresponding to the shipped
Qt for Python runtime; it is not a link to the generic Qt home page.

| Distributed component | Exact source | Official retrieval URL | SHA-256 evidence |
| --- | --- | --- | --- |
| PySide6 6.11.1 | `pyside-setup-everywhere-src-6.11.1.tar.xz` | `https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/pyside-setup-everywhere-src-6.11.1.tar.xz` | `6FFD9835BB0DD2C56F061D62F1616BB1707CFC0202B80E3165D6BE087F3965E2` |
| shiboken6 6.11.1 | Same `pyside-setup` source release (Shiboken source is part of that tree) | `https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/pyside-setup-everywhere-src-6.11.1.tar.xz` | `6FFD9835BB0DD2C56F061D62F1616BB1707CFC0202B80E3165D6BE087F3965E2` |
| Qt Runtime 6.11.1 | Exact Qt 6.11.1 submodule source archives | `https://download.qt.io/official_releases/qt/6.11/6.11.1/submodules/` | Per-archive values below and in the verified inventory |

## Qt Runtime source modules

The exact source archives verified for the frozen package are listed in
[`third_party/source-information/qt-source-requirements.json`](../../third_party/source-information/qt-source-requirements.json).
They are the source-of-record for filename, official direct URL, local evidence
path and SHA-256.  The archives cover: `qt3d`, `qtbase`, `qtcharts`,
`qtdatavis3d`, `qtdeclarative`, `qtgraphs`, `qtlocation`, `qtmultimedia`,
`qtpositioning`, `qtquick3d`, `qtquicktimeline`, `qtremoteobjects`, `qtscxml`,
`qtsensors`, `qtshadertools`, `qtspeech`, `qtsvg`, `qtvirtualkeyboard`,
`qtwebchannel`, `qtwebengine`, `qtwebsockets`, and `qtwebview`.

The LGPL candidate removes the GPL-only `qtgraphs`, `qtquick3d`,
`qtquicktimeline`, and `qtvirtualkeyboard` runtime groups in its isolated
staging copy.  Their source records remain retained as audit evidence; they do
not imply that those groups remain in a future LGPL distribution.

Qt Multimedia's separately attributed FFmpeg source remains recorded in the
existing closed Qt Multimedia evidence; this Qt route review does not alter it.

## Recipient-facing availability material

Before a future public LGPL release is assembled, include this document (or its
equivalent notice) with the release notices, the LGPLv3 text, Qt attribution,
and the exact URLs above.  The repository retains the matching hash and source
inventory records, but a recipient must not be sent only to a generic product
homepage.

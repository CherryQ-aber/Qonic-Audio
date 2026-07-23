# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

SPEC_PATH = Path(globals().get("__file__", Path.cwd() / "Qonic_Audio.spec")).resolve()
SPEC_DIR = SPEC_PATH.parent

if str(SPEC_DIR) not in sys.path:
    sys.path.insert(0, str(SPEC_DIR))

from app_info import APP_PACKAGE_BASENAME

a = Analysis(
    ['main_qml.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui_next/qml', 'ui_next/qml'),
        ('Assets/icon.ico', 'Assets'),
        ('Tools/ffmpeg/bin/ffmpeg.exe', 'Tools/ffmpeg/bin'),
        ('Tools/ffmpeg/bin/ffprobe.exe', 'Tools/ffmpeg/bin'),
        ('Tools/ncmdump/ncmdump.exe', 'Tools/ncmdump'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_PACKAGE_BASENAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Assets\\icon.ico'],
    version='windows_version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_PACKAGE_BASENAME,
)

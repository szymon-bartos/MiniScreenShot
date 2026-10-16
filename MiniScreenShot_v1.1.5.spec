# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, SPECPATH)
from tk_runtime import prepare_tk_runtime

prepare_tk_runtime(Path(SPECPATH) / 'build' / 'tk-runtime')
a = Analysis(
    ['app_advanced.py'], pathex=[SPECPATH], binaries=[],
    datas=[(str(Path(SPECPATH) / 'assets' / 'capture-frame.png'), 'assets'),
           (str(Path(SPECPATH) / 'assets' / 'capture-frame.ico'), 'assets'),
           (str(Path(SPECPATH) / 'LICENSE.txt'), '.')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='MiniScreenShot_v1.1.5', icon=str(Path(SPECPATH) / 'assets' / 'capture-frame.ico'),
    version=str(Path(SPECPATH) / 'version_info.txt'),
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, uac_admin=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MiniScreenShot_v1.1.5')

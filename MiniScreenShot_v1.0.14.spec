# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, SPECPATH)
from tk_runtime import prepare_tk_runtime

prepare_tk_runtime(Path(SPECPATH) / 'build' / 'tk-runtime')
a = Analysis(
    ['app_advanced.py'], pathex=[SPECPATH], binaries=[],
    datas=[(str(Path(SPECPATH) / 'assets' / 'capture-frame.png'), 'assets'),
           (str(Path(SPECPATH) / 'assets' / 'capture-frame.ico'), 'assets')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='MiniScreenShot_v1.0.14', icon=str(Path(SPECPATH) / 'assets' / 'capture-frame.ico'),
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)

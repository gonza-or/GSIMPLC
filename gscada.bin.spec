# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gscada_main.py'],
    pathex=[],
    binaries=[],
    datas=[('gscada/static', 'gscada/static'), ('gscada/configs', 'gscada/configs')],
    hiddenimports=['pymodbus', 'fastapi', 'uvicorn', 'pydantic', 'yaml'],
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
    a.binaries,
    a.datas,
    [],
    name='gscada.bin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['detect.py'],
    pathex=[],
    binaries=[],
    datas=[('templates_enter', 'templates_enter'), ('templates_ingame', 'templates_ingame'), ('templates_skip', 'templates_skip'), ('templates_special', 'templates_special'), ('templates_steps', 'templates_steps')],
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
    a.binaries,
    a.datas,
    [],
    name='detect',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

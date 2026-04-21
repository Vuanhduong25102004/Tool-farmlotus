# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['detect.py'],
    pathex=[],
    binaries=[],
    datas=[('logo.ico', '.'), ('theme.qss', '.')],
    hiddenimports=['cv2', 'numpy', 'mss', 'pygetwindow', 'keyboard', 'pydirectinput', 'requests', 'PyQt6', 'pygame', 'qtawesome', 'psutil'],
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
    name='Farmsen',
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
    uac_admin=True,
    icon=['logo.ico'],
)

# -*- mode: python ; coding: utf-8 -*-
# Genera un solo archivo: dist/InventarioEnfermeria.exe
# Sin datos del inventario: viven en %LOCALAPPDATA%\InventarioEnfermeria de cada computadora.

a = Analysis(
    ['inventario.py'],
    pathex=[],
    binaries=[],
    datas=[('app/recursos', 'app/recursos')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest'],
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
    name='InventarioEnfermeria',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app/recursos/icono.ico'],
)

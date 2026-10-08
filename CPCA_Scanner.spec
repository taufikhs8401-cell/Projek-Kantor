# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['menu_utama_umanew.py'],
    pathex=[],
    binaries=[],
    datas=[('menu_utama_uma.ui', '.'), ('insert_uma.ui', '.'), ('edit_uma.ui', '.'), ('export.ui', '.'), ('downloader.ui', '.'), ('batch_insert.ui', '.'), ('insert_etf.ui', '.'), ('edit_etf.ui', '.'), ('batch_etf.ui', '.'), ('export_etf.ui', '.'), ('insert_suspend.ui', '.'), ('edit_suspend.ui', '.'), ('downloader_suspend.ui', '.'), ('batch_suspend.ui', '.'), ('export_suspend.ui', '.'), ('downloader_teoretis.ui', '.')],
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
    name='CPCA_Scanner',
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

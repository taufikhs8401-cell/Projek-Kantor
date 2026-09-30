# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# ============================================================
# KOLEKSI DEPENDENCIES
# ============================================================
datas_pdf, binaries_pdf, hidden_pdf = collect_all('pdfplumber')
datas_mysql, binaries_mysql, hidden_mysql = collect_all('mysql.connector')
datas_sel, binaries_sel, hidden_sel = collect_all('selenium')
datas_uc, binaries_uc, hidden_uc = collect_all('undetected_chromedriver')
datas_qt, binaries_qt, hidden_qt = collect_all('PyQt5')

# ============================================================
# FILE .UI YANG HARUS DI-INCLUDE
# ============================================================
ui_files = [
    ('menu_utama_uma.ui', '.'),
    ('insert_uma.ui', '.'),
    ('edit_uma.ui', '.'),
    ('export.ui', '.'),
    ('downloader.ui', '.'),
    ('batch_insert.ui', '.'),
    ('insert_etf.ui', '.'),
    ('edit_etf.ui', '.'),
    ('batch_etf.ui', '.'),
    ('export_etf.ui', '.'),
    ('insert_suspend.ui', '.'),
    ('edit_suspend.ui', '.'),
    ('downloader_suspend.ui', '.'),
    ('batch_suspend.ui', '.'),
    ('export_suspend.ui', '.'),
    ('downloader_teoretis.ui', '.'),
]

# Gabungkan
datas = datas_pdf + datas_mysql + datas_sel + datas_uc + datas_qt + ui_files
binaries = binaries_pdf + binaries_mysql + binaries_sel + binaries_uc + binaries_qt
hiddenimports = (
    hidden_pdf + hidden_mysql + hidden_sel + hidden_uc + hidden_qt +
    [
        'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.uic',
        'PIL', 'PIL.Image',
        'pdfminer', 'pdfminer.high_level', 'pdfminer.layout',
        'pdfminer.pdfinterp', 'pdfminer.pdfpage', 'pdfminer.pdfparser',
        'pdfminer.converter', 'pdfminer.image',
        'pypdfium2', 'cryptography', 'cffi',
        'charset_normalizer', 'idna', 'urllib3', 'certifi',
    ]
)

block_cipher = None

a = Analysis(
    ['menu_utama_umanew.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CPCA_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,           # ← WAJIB: agar error terlihat
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CPCA_Scanner',
)
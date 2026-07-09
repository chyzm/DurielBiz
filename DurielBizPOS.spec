# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('accounts', 'accounts'), ('cloudsync', 'cloudsync'), ('inventory', 'inventory'), ('invoicing', 'invoicing'), ('licensing', 'licensing'), ('notifications', 'notifications'), ('pos_system', 'pos_system'), ('products', 'products'), ('purchases', 'purchases'), ('reports', 'reports'), ('sales', 'sales'), ('suppliers', 'suppliers'), ('templates', 'templates'), ('static', 'static'), ('manage.py', '.'), ('.env', '.')]
datas += collect_data_files('tzdata')


a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['django.core.management.commands.runserver', 'django.core.management.commands.migrate', 'django.contrib.staticfiles.management.commands.runserver', 'whitenoise.middleware'],
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
    name='DurielBizPOS',
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

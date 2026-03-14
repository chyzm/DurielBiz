# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('accounts', 'accounts'), ('inventory', 'inventory'), ('notifications', 'notifications'), ('pos_system', 'pos_system'), ('products', 'products'), ('purchases', 'purchases'), ('reports', 'reports'), ('sales', 'sales'), ('suppliers', 'suppliers'), ('templates', 'templates'), ('static', 'static'), ('manage.py', '.')]
datas += collect_data_files('tzdata')


a = Analysis(
    ['desktop_sync_service.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['django.core.management.commands.migrate', 'win32timezone'],
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
    name='DurielBizPOSSyncService',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DurielBizPOSSyncService',
)

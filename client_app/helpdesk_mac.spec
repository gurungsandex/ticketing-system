# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for macOS — builds a .app bundle
# Run from client_app/:  pyinstaller helpdesk_mac.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'requests',
        'uuid',
        'socket',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['winreg'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HelpdeskClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name='HelpdeskClient',
)

app = BUNDLE(
    coll,
    name='HelpdeskClient.app',
    icon=None,
    bundle_identifier='com.mom.helpdesk.client',
    info_plist={
        'CFBundleDisplayName': 'MOM IT Helpdesk',
        'CFBundleName': 'MOM IT Helpdesk',
        'CFBundleShortVersionString': '4.0',
        'CFBundleVersion': '4.0.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'Medical Offices of Manhattan',
        'LSMinimumSystemVersion': '11.0',
    },
)

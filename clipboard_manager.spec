# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['clipboard_manager/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('clipboard_manager/resources', 'clipboard_manager/resources'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'ctypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.Qt3D',
        'PySide6.QtWebEngine', 'PySide6.QtWebChannel', 'PySide6.QtMultimedia',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSerialPort',
        'PySide6.QtSensors', 'PySide6.QtPositioning', 'PySide6.QtLocation',
        'PySide6.QtRemoteObjects', 'PySide6.QtTextToSpeech',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization',
    ],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='ClipboardManager', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='clipboard_manager/resources/icons/app.ico',
)

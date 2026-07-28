# -*- mode: python ; coding: utf-8 -*-
"""Сборка KPGEN ESTP в исполняемый файл."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH)

# faster-whisper тянет нативные библиотеки ctranslate2 и onnxruntime —
# без явного сбора они не попадают в дистрибутив.
binaries = []
for package in ("ctranslate2", "onnxruntime", "tokenizers"):
    try:
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass

hiddenimports = [
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "tokenizers",
    "av",
    "docx",
    "pptx",
]
for package in ("faster_whisper", "onnxruntime"):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

datas = [
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "assets"), "assets"),
]

# Ресурсы моделей faster-whisper (файл конфигурации VAD).
try:
    import faster_whisper
    assets_dir = Path(faster_whisper.__file__).parent / "assets"
    if assets_dir.exists():
        datas.append((str(assets_dir), "faster_whisper/assets"))
except Exception:
    pass


a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "scipy", "pandas", "numpy.testing",
        "PySide6.QtWebEngineCore", "PySide6.QtQuick", "PySide6.Qt3D",
        "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "tkinter", "test", "unittest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KPGEN ESTP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KPGEN ESTP",
)

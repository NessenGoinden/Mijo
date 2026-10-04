# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller pour Nourriture.app (macOS)."""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT))
from nourriture import __version__  # noqa: E402

datas = [(str(ROOT / "nourriture" / "static"), "nourriture/static")]
binaries = []
hiddenimports = ["nourriture", "nourriture.app", "nourriture.server", "objc", "Foundation", "AppKit", "WebKit", "Quartz", "Vision",
                 "multipart", "python_multipart", "PIL._tkinter_finder"]

for pkg in ("faster_whisper", "ctranslate2", "av", "tokenizers", "onnxruntime", "huggingface_hub", "yt_dlp", "webview", "uvicorn",
            "fastapi", "starlette", "anyio", "pydantic", "pydantic_core", "httpx", "httpcore", "h11", "certifi", "sniffio", "idna",
            "python_multipart", "multipart"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:  # paquet absent ou sans données
        print(f"[spec] collect_all({pkg}) ignoré : {e}")

hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("nourriture")
hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "IPython", "jupyter", "torch", "tensorflow", "PyQt5", "PyQt6", "PySide2", "PySide6", "gi", "wx"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Nourriture",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Nourriture")

app = BUNDLE(
    coll,
    name="Nourriture.app",
    icon=str(ROOT / "packaging" / "Nourriture.icns"),
    bundle_identifier="fr.nourriture.app",
    version=__version__,
    info_plist={
        "CFBundleName": "Nourriture",
        "CFBundleDisplayName": "Nourriture",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "LSApplicationCategoryType": "public.app-category.food-and-drink",
        "NSHumanReadableCopyright": "Logiciel libre — fonctionne entièrement en local.",
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "NSRequiresAquaSystemAppearance": False,
    },
)

# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the packaged desktop app.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_dir = Path(os.getcwd())
backend_dir = project_dir / "backend"
icon_path = project_dir / "resources" / "app.icns"

webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")
pypdf_datas, pypdf_binaries, pypdf_hiddenimports = collect_all("pypdf")

hiddenimports = [
    "main",
    "webview",
    "webview.platforms",
    "webview.platforms.cocoa",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.responses",
    "fastapi.staticfiles",
    "starlette",
    "starlette.middleware",
    "starlette.responses",
    "starlette.routing",
    "starlette.staticfiles",
    "pydantic",
    "multipart",
    "pdf2image",
    "pdf2image.exceptions",
    "PIL",
    "PIL.Image",
    "pypdf",
    "httpx",
    "converters",
    "converters.pptx_to_pdf",
    "converters.pdf_to_images",
    "converters.slide_extractor",
    "utils",
    "utils.file_manager",
] + webview_hiddenimports + pypdf_hiddenimports

datas = [
    (str(project_dir / "frontend_dist"), "frontend_dist"),
    (str(backend_dir / "main.py"), "."),
    (str(backend_dir / "__init__.py"), "."),
    (str(backend_dir / "converters"), "converters"),
    (str(backend_dir / "utils"), "utils"),
] + webview_datas + pypdf_datas

a = Analysis(
    ["launcher.py"],
    pathex=[str(project_dir), str(backend_dir)],
    binaries=webview_binaries + pypdf_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MyApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MyApp",
)

app = BUNDLE(
    coll,
    name="MyApp.app",
    bundle_identifier="com.myapp.desktop",
    info_plist={
        "CFBundleName": "MyApp",
        "CFBundleDisplayName": "MyApp",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
    icon=str(icon_path) if icon_path.exists() else None,
)

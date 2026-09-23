# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows build of SlideDrop."""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_dir = Path(os.getcwd())
backend_dir = project_dir / "backend"
icon_path = project_dir / "resources" / "app.ico"

webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")
pypdf_datas, pypdf_binaries, pypdf_hiddenimports = collect_all("pypdf")
fitz_datas, fitz_binaries, fitz_hiddenimports = collect_all("fitz")

hiddenimports = [
    "main",
    "platform_services",
    "prompt_builder",
    "webview",
    "webview.platforms",
    "webview.platforms.winforms",
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
    "fitz",
    "httpx",
    "converters",
    "converters.pptx_to_pdf",
    "converters.pdf_to_images",
    "converters.slide_extractor",
    "utils",
    "utils.file_manager",
] + webview_hiddenimports + pypdf_hiddenimports + fitz_hiddenimports

datas = [
    (str(project_dir / "frontend_dist"), "frontend_dist"),
    (str(backend_dir / "main.py"), "."),
    (str(backend_dir / "platform_services.py"), "."),
    (str(backend_dir / "prompt_builder.py"), "."),
    (str(backend_dir / "__init__.py"), "."),
    (str(backend_dir / "converters"), "converters"),
    (str(backend_dir / "utils"), "utils"),
] + webview_datas + pypdf_datas + fitz_datas

a = Analysis(
    ["launcher.py"],
    pathex=[str(project_dir), str(backend_dir)],
    binaries=webview_binaries + pypdf_binaries + fitz_binaries,
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
    name="SlideDrop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SlideDrop",
)


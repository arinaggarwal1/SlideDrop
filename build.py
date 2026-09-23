#!/usr/bin/env python3
"""Reproducible native build pipeline for macOS and Windows.

Run this file on the target OS. PyInstaller intentionally creates native
artifacts, so CI runs the same script once on macOS and once on Windows.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
    print(f"→ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)


def require_command(command: str, install_hint: str):
    if shutil.which(command):
        return
    raise RuntimeError(f"Missing command '{command}'. {install_hint}")


def require_python_module(module_name: str, install_hint: str):
    try:
        __import__(module_name)
    except Exception as exc:
        raise RuntimeError(f"Missing Python module '{module_name}'. {install_hint}") from exc


def require_pywebview():
    try:
        import webview  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "Missing Python module 'pywebview'. Install with: "
            f"{sys.executable} -m pip install pywebview"
        ) from exc


def clean(paths: list[Path]):
    for path in paths:
        if path.exists():
            print(f"• Removing {path}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def build_frontend(frontend_dir: Path):
    require_command("npm", "Install Node.js 20 or newer.")
    npm_command = shutil.which("npm") or "npm"
    env = {**os.environ, "SLIDEDROP_DESKTOP_BUILD": "1"}
    run([npm_command, "ci"], cwd=frontend_dir, env=env)
    run([npm_command, "run", "build"], cwd=frontend_dir, env=env)


def copy_frontend_dist(frontend_out: Path, frontend_dist: Path):
    if not frontend_out.exists():
        raise RuntimeError(f"Frontend export not found at {frontend_out}")
    shutil.copytree(frontend_out, frontend_dist, dirs_exist_ok=True)


def build_app(root_dir: Path, spec_file: Path):
    require_python_module(
        "PyInstaller",
        f"Install with: {sys.executable} -m pip install pyinstaller",
    )
    require_pywebview()
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(spec_file),
            "--noconfirm",
            "--clean",
        ],
        cwd=root_dir,
    )


def create_dmg(app_name: str, dist_dir: Path):
    require_command("create-dmg", "Install with: brew install create-dmg")

    app_path = dist_dir / f"{app_name}.app"
    dmg_path = dist_dir / f"{app_name}.dmg"
    staging_dir = dist_dir / "_dmg_staging"

    if not app_path.exists():
        raise RuntimeError(f"Expected app bundle at {app_path}")

    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_path, staging_dir / app_path.name)
    if dmg_path.exists():
        dmg_path.unlink()

    dmg_env = dict(os.environ)
    dmg_env["LANG"] = "en_US.UTF-8"
    dmg_env["LC_ALL"] = "en_US.UTF-8"
    dmg_env["LC_CTYPE"] = "en_US.UTF-8"

    run(
        [
            "create-dmg",
            "--volname",
            app_name,
            "--window-pos",
            "200",
            "120",
            "--window-size",
            "900",
            "520",
            "--icon-size",
            "120",
            "--icon",
            f"{app_name}.app",
            "220",
            "250",
            "--hide-extension",
            f"{app_name}.app",
            "--app-drop-link",
            "680",
            "250",
            str(dmg_path),
            str(staging_dir),
        ],
        env=dmg_env,
    )

    shutil.rmtree(staging_dir, ignore_errors=True)


def create_windows_archive(app_name: str, dist_dir: Path) -> Path:
    """Package the PyInstaller folder as a portable Windows distribution."""
    app_dir = dist_dir / app_name
    exe_path = app_dir / f"{app_name}.exe"
    archive_path = dist_dir / f"{app_name}-Windows.zip"
    if not exe_path.exists():
        raise RuntimeError(f"Expected Windows executable at {exe_path}")

    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in app_dir.rglob("*"):
            if source.is_file():
                archive.write(source, Path(app_name) / source.relative_to(app_dir))
    return archive_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SlideDrop for the current desktop OS.")
    parser.add_argument("--app-name", default="SlideDrop", help="Output app name")
    parser.add_argument(
        "--spec",
        default=None,
        help="Optional PyInstaller spec override; normally selected automatically.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    root_dir = Path(__file__).resolve().parent
    frontend_dir = root_dir / "frontend"
    frontend_out = frontend_dir / "out"
    frontend_dist = root_dir / "frontend_dist"
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    if sys.platform == "darwin":
        platform_name = "macOS"
        default_spec = "SlideDrop.spec"
    elif sys.platform == "win32":
        platform_name = "Windows"
        default_spec = "SlideDrop.windows.spec"
    else:
        raise RuntimeError("Desktop builds are supported on macOS and Windows only.")

    spec_file = root_dir / (args.spec or default_spec)

    if not spec_file.exists():
        raise RuntimeError(f"Spec file not found: {spec_file}")

    print("=" * 56)
    print(f"Building {args.app_name} for {platform_name}")
    print("=" * 56)

    clean([dist_dir, build_dir, frontend_dist])
    build_frontend(frontend_dir)
    frontend_dist.mkdir(parents=True, exist_ok=True)
    copy_frontend_dist(frontend_out, frontend_dist)
    build_app(root_dir, spec_file)
    if sys.platform == "darwin":
        create_dmg(args.app_name, dist_dir)
        outputs = [dist_dir / f"{args.app_name}.app", dist_dir / f"{args.app_name}.dmg"]
    else:
        outputs = [dist_dir / args.app_name, create_windows_archive(args.app_name, dist_dir)]

    print()
    print("Build complete")
    for output in outputs:
        print(f"Output: {output}")


if __name__ == "__main__":
    main()

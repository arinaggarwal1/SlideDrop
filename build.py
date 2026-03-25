#!/usr/bin/env python3
"""
Reproducible macOS desktop build pipeline.

Run:
    python build.py

Outputs:
    dist/MyApp.app
    dist/MyApp.dmg
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
    require_command("npm", "Install Node.js: brew install node")
    env = {**os.environ, "SLIDEDROP_DESKTOP_BUILD": "1"}
    run(["npm", "ci"], cwd=frontend_dir, env=env)
    run(["npm", "run", "build"], cwd=frontend_dir, env=env)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build macOS app + DMG for this project.")
    parser.add_argument("--app-name", default="MyApp", help="Output app name (default: MyApp)")
    parser.add_argument("--spec", default="MyApp.spec", help="PyInstaller spec file (default: MyApp.spec)")
    return parser.parse_args()


def main():
    args = parse_args()

    root_dir = Path(__file__).resolve().parent
    frontend_dir = root_dir / "frontend"
    frontend_out = frontend_dir / "out"
    frontend_dist = root_dir / "frontend_dist"
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    spec_file = root_dir / args.spec

    if not spec_file.exists():
        raise RuntimeError(f"Spec file not found: {spec_file}")

    print("=" * 56)
    print(f"Building desktop app: {args.app_name}")
    print("=" * 56)

    clean([dist_dir, build_dir, frontend_dist])
    build_frontend(frontend_dir)
    frontend_dist.mkdir(parents=True, exist_ok=True)
    copy_frontend_dist(frontend_out, frontend_dist)
    build_app(root_dir, spec_file)
    create_dmg(args.app_name, dist_dir)

    app_output = dist_dir / f"{args.app_name}.app"
    dmg_output = dist_dir / f"{args.app_name}.dmg"

    print()
    print("Build complete")
    print(f"App: {app_output}")
    print(f"DMG: {dmg_output}")


if __name__ == "__main__":
    main()

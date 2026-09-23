"""
PPTX to PDF converter using LibreOffice headless mode.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path


class LibreOfficeNotFoundError(Exception):
    """Raised when LibreOffice is not installed or not found in PATH."""
    pass


class ConversionError(Exception):
    """Raised when the PPTX to PDF conversion fails."""
    pass


def find_libreoffice() -> str:
    """Find the LibreOffice binary on the system."""
    # Common locations on macOS
    mac_paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/opt/homebrew/bin/soffice",
        "/usr/local/bin/soffice",
        "/opt/homebrew/bin/libreoffice",
        "/usr/local/bin/libreoffice",
    ]

    # Check if soffice is in PATH
    soffice_path = shutil.which("soffice")
    if soffice_path:
        return soffice_path

    # Check common macOS locations
    for path in mac_paths:
        if Path(path).exists():
            return path

    # Standard Windows installers place soffice.exe under Program Files.
    for environment_name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        program_files = os.environ.get(environment_name)
        if not program_files:
            continue
        windows_path = Path(program_files) / "LibreOffice" / "program" / "soffice.exe"
        if windows_path.exists():
            return str(windows_path)

    # Check Linux paths
    libreoffice_path = shutil.which("libreoffice")
    if libreoffice_path:
        return libreoffice_path

    raise LibreOfficeNotFoundError(
        "LibreOffice is not installed or not found. "
        "Please install it:\n"
        "  macOS:  brew install --cask libreoffice\n"
        "  Linux:  sudo apt install libreoffice\n"
        "  Windows: Download from https://www.libreoffice.org/download/"
    )


def _build_pdf_filter(page_range: str | None = None) -> str:
    """Build an Impress PDF export filter string for LibreOffice."""
    filter_options: dict[str, dict[str, str]] = {}
    if page_range:
        filter_options["PageRange"] = {"type": "string", "value": page_range}

    if not filter_options:
        return "pdf"

    return f"pdf:impress_pdf_Export:{json.dumps(filter_options, separators=(',', ':'))}"


def convert_pptx_to_pdf(
    pptx_path: str,
    output_dir: str,
    page_range: str | None = None,
    output_basename: str | None = None,
) -> str:
    """
    Convert a PPTX file to PDF using LibreOffice headless.

    Args:
        pptx_path: Path to the input PPTX file.
        output_dir: Directory where the PDF will be saved.
        page_range: Optional slide range to export, e.g. "38-41".
        output_basename: Optional output PDF basename without extension.

    Returns:
        Path to the generated PDF file.

    Raises:
        LibreOfficeNotFoundError: If LibreOffice is not installed.
        ConversionError: If the conversion fails.
    """
    soffice = find_libreoffice()
    pptx_file = Path(pptx_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target_stem = (output_basename or pptx_file.stem).strip() or pptx_file.stem
    expected_pdf = out_dir / f"{target_stem}.pdf"

    try:
        if expected_pdf.exists():
            expected_pdf.unlink()

        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                _build_pdf_filter(page_range),
                "--outdir", str(out_dir),
                str(pptx_file),
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            raise ConversionError(
                f"LibreOffice conversion failed:\n{result.stderr}"
            )

        generated_pdf = out_dir / f"{pptx_file.stem}.pdf"
        if not generated_pdf.exists():
            raise ConversionError(
                f"PDF was not generated at expected path: {expected_pdf}"
            )

        if generated_pdf != expected_pdf:
            if expected_pdf.exists():
                expected_pdf.unlink()
            generated_pdf.rename(expected_pdf)

        return str(expected_pdf)

    except subprocess.TimeoutExpired:
        raise ConversionError("Conversion timed out after 5 minutes.")
    except FileNotFoundError:
        raise LibreOfficeNotFoundError(
            f"LibreOffice binary not found at: {soffice}"
        )

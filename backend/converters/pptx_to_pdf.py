"""
PPTX to PDF converter using LibreOffice headless mode.
"""

import subprocess
import shutil
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
        "/usr/local/bin/soffice",
    ]

    # Check if soffice is in PATH
    soffice_path = shutil.which("soffice")
    if soffice_path:
        return soffice_path

    # Check common macOS locations
    for path in mac_paths:
        if Path(path).exists():
            return path

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


def convert_pptx_to_pdf(pptx_path: str, output_dir: str) -> str:
    """
    Convert a PPTX file to PDF using LibreOffice headless.

    Args:
        pptx_path: Path to the input PPTX file.
        output_dir: Directory where the PDF will be saved.

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

    try:
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to", "pdf",
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

        # Find the generated PDF
        expected_pdf = out_dir / f"{pptx_file.stem}.pdf"
        if not expected_pdf.exists():
            raise ConversionError(
                f"PDF was not generated at expected path: {expected_pdf}"
            )

        return str(expected_pdf)

    except subprocess.TimeoutExpired:
        raise ConversionError("Conversion timed out after 5 minutes.")
    except FileNotFoundError:
        raise LibreOfficeNotFoundError(
            f"LibreOffice binary not found at: {soffice}"
        )

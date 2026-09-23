"""
PDF to images converter using pdf2image (poppler).
Renders each page at 300 DPI and saves as slide_N.png.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError


class PopplerNotFoundError(Exception):
    """Raised when Poppler is not installed."""
    pass


class PDFConversionError(Exception):
    """Raised when PDF to image conversion fails."""
    pass


def find_poppler_path() -> Optional[str]:
    """Return the Poppler bin directory when pdfinfo is available."""
    env_value = os.environ.get("SLIDEDROP_POPPLER_PATH", "").strip()
    if env_value:
        env_path = Path(env_value).expanduser()
        if env_path.is_file():
            return str(env_path.parent)
        if (env_path / "pdfinfo").exists():
            return str(env_path)

    pdfinfo_candidates = [
        shutil.which("pdfinfo"),
        "/opt/homebrew/bin/pdfinfo",
        "/opt/homebrew/opt/poppler/bin/pdfinfo",
        "/usr/local/bin/pdfinfo",
        "/usr/local/opt/poppler/bin/pdfinfo",
    ]

    for candidate in pdfinfo_candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).parent)

    return None


# Lazily resolved so launcher.py configure_runtime() has time to patch PATH
# before the first lookup.  The module-level constant previously ran at import
# time, *before* PATH was fixed, causing the bundled .app to always get None.
_poppler_path_cache: Optional[str] = None
_poppler_path_resolved: bool = False


def _get_poppler_path() -> Optional[str]:
    """Return the cached poppler path, resolving it on first call."""
    global _poppler_path_cache, _poppler_path_resolved
    if not _poppler_path_resolved:
        _poppler_path_cache = find_poppler_path()
        _poppler_path_resolved = True
    return _poppler_path_cache


def _poppler_install_message() -> str:
    discovered = _get_poppler_path() or "not found"
    return (
        "Poppler is not installed. Please install it:\n"
        "  macOS:  brew install poppler\n"
        "  Linux:  sudo apt install poppler-utils\n"
        "  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases\n"
        f"Resolved poppler_path: {discovered}"
    )


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the number of pages in a PDF without converting.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Number of pages in the PDF.
    """
    if sys.platform == "win32":
        try:
            import fitz

            with fitz.open(pdf_path) as document:
                return document.page_count
        except ImportError as exc:
            raise PopplerNotFoundError(
                "The Windows PDF renderer is missing. Reinstall SlideDrop or install PyMuPDF."
            ) from exc
        except Exception as exc:
            raise PDFConversionError(f"Failed to read PDF info: {exc}") from exc

    try:
        info = pdfinfo_from_path(pdf_path, poppler_path=_get_poppler_path())
        return info["Pages"]
    except PDFInfoNotInstalledError as exc:
        raise PopplerNotFoundError(_poppler_install_message()) from exc
    except Exception as e:
        raise PDFConversionError(f"Failed to read PDF info: {e}")


def convert_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """
    Convert each page of a PDF to a PNG image at the specified DPI.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory where images will be saved.
        dpi: Resolution for rendering (default 300).
        on_progress: Optional callback(current_page, total_pages).

    Returns:
        List of paths to generated image files.

    Raises:
        PopplerNotFoundError: If Poppler is not installed.
        PDFConversionError: If conversion fails.
    """
    if sys.platform == "win32":
        return _convert_pdf_to_images_windows(pdf_path, output_dir, dpi, on_progress)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        total_pages = get_pdf_page_count(pdf_path)
    except PopplerNotFoundError:
        raise
    except Exception:
        total_pages = 0

    image_paths: list[str] = []

    try:
        pages_info = get_pdf_page_count(pdf_path) if total_pages == 0 else total_pages

        for page_num in range(1, pages_info + 1):
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_num,
                last_page=page_num,
                fmt="png",
                poppler_path=_get_poppler_path(),
            )

            if images:
                image_filename = f"slide_{page_num}.png"
                image_path = out_dir / image_filename
                images[0].save(str(image_path), "PNG")
                image_paths.append(str(image_path))

            if on_progress:
                on_progress(page_num, pages_info)

        return image_paths

    except PDFInfoNotInstalledError as exc:
        raise PopplerNotFoundError(_poppler_install_message()) from exc
    except Exception as e:
        raise PDFConversionError(f"Failed to convert PDF to images: {e}")


def _convert_pdf_to_images_windows(
    pdf_path: str,
    output_dir: str,
    dpi: int,
    on_progress: Optional[Callable[[int, int], None]],
) -> list[str]:
    """Render PDFs with PyMuPDF on Windows, avoiding a separate Poppler install."""
    try:
        import fitz
    except ImportError as exc:
        raise PopplerNotFoundError(
            "The Windows PDF renderer is missing. Reinstall SlideDrop or install PyMuPDF."
        ) from exc

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[str] = []
    scale = dpi / 72

    try:
        with fitz.open(pdf_path) as document:
            total_pages = document.page_count
            matrix = fitz.Matrix(scale, scale)
            for page_index, page in enumerate(document, start=1):
                image_path = out_dir / f"slide_{page_index}.png"
                page.get_pixmap(matrix=matrix, alpha=False).save(str(image_path))
                image_paths.append(str(image_path))
                if on_progress:
                    on_progress(page_index, total_pages)
        return image_paths
    except Exception as exc:
        raise PDFConversionError(f"Failed to convert PDF to images: {exc}") from exc

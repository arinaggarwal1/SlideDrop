"""
PDF to images converter using pdf2image (poppler).
Renders each page at 300 DPI and saves as slide_N.png.
"""

from pathlib import Path
from typing import Callable, Optional

from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError


class PopplerNotFoundError(Exception):
    """Raised when Poppler is not installed."""
    pass


class PDFConversionError(Exception):
    """Raised when PDF to image conversion fails."""
    pass


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the number of pages in a PDF without converting.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Number of pages in the PDF.
    """
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(pdf_path)
        return info["Pages"]
    except PDFInfoNotInstalledError:
        raise PopplerNotFoundError(
            "Poppler is not installed. Please install it:\n"
            "  macOS:  brew install poppler\n"
            "  Linux:  sudo apt install poppler-utils\n"
            "  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases"
        )
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
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        total_pages = get_pdf_page_count(pdf_path)
    except PopplerNotFoundError:
        raise
    except Exception:
        total_pages = 0  # Will discover during conversion

    image_paths: list[str] = []

    try:
        # Convert one page at a time for progress tracking
        pages_info = get_pdf_page_count(pdf_path) if total_pages == 0 else total_pages

        for page_num in range(1, pages_info + 1):
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_num,
                last_page=page_num,
                fmt="png",
            )

            if images:
                image_filename = f"slide_{page_num}.png"
                image_path = out_dir / image_filename
                images[0].save(str(image_path), "PNG")
                image_paths.append(str(image_path))

            if on_progress:
                on_progress(page_num, pages_info)

        return image_paths

    except PDFInfoNotInstalledError:
        raise PopplerNotFoundError(
            "Poppler is not installed. Please install it:\n"
            "  macOS:  brew install poppler\n"
            "  Linux:  sudo apt install poppler-utils\n"
            "  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases"
        )
    except Exception as e:
        raise PDFConversionError(f"Failed to convert PDF to images: {e}")

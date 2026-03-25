"""
File management utilities for SlideDrop.
Handles Downloads folder detection, output directory creation, and temp file cleanup.
"""

import tempfile
import shutil
from pathlib import Path


def get_downloads_folder() -> Path:
    """Get the user's Downloads folder path."""
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def create_output_directory(filename: str, custom_output_dir: str | None = None) -> Path:
    """
    Create an output directory based on the uploaded file name.
    If custom_output_dir is provided, base the directory there instead of Downloads.

    Example: 'Lecture5.pptx' → ~/Downloads/Lecture5_slides/ (or /custom/path/Lecture5_slides/)

    If the directory already exists, appends _1, _2, etc.

    Args:
        filename: Original uploaded file name (with extension).
        custom_output_dir: Optional custom base directory path.

    Returns:
        Path to the created output directory.
    """
    if custom_output_dir:
        base_dir = Path(custom_output_dir).expanduser().resolve()
        if not base_dir.exists():
            base_dir.mkdir(parents=True, exist_ok=True)
    else:
        base_dir = get_downloads_folder()

    stem = Path(filename).stem
    base_name = f"{stem}_slides"
    output_dir = base_dir / base_name

    # Handle name collisions
    if output_dir.exists():
        counter = 1
        while True:
            output_dir = base_dir / f"{base_name}_{counter}"
            if not output_dir.exists():
                break
            counter += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def create_temp_directory() -> str:
    """Create a temporary directory for intermediate files."""
    return tempfile.mkdtemp(prefix="slidedrop_")


def cleanup_temp_directory(temp_dir: str) -> None:
    """Remove a temporary directory and all its contents."""
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass  # Best effort cleanup


def get_file_extension(filename: str) -> str:
    """Get the lowercase file extension (e.g., '.pptx')."""
    return Path(filename).suffix.lower()


def is_supported_file(filename: str) -> bool:
    """Check if the file type is supported."""
    return get_file_extension(filename) in {".pptx", ".pdf"}

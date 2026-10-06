"""Bounded, on-demand thumbnails using the app's existing PDF renderers."""

import io
import sys
import threading
from functools import lru_cache

from pdf2image import convert_from_path
from PIL import Image
from converters.pdf_to_images import find_poppler_path

_render_slots = threading.BoundedSemaphore(2)


@lru_cache(maxsize=128)
def render_preview(path: str, page: int, modified: int, size: int) -> bytes:
    # File metadata forms part of the key so edits invalidate cached thumbnails.
    with _render_slots:
        if sys.platform == "win32":
            import fitz
            with fitz.open(path) as document:
                source = document[page - 1]
                scale = 720 / max(source.rect.width, source.rect.height)
                pixmap = source.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        else:
            image = convert_from_path(
                path, first_page=page, last_page=page, size=720,
                fmt="jpeg", thread_count=1, timeout=30,
                poppler_path=find_poppler_path(),
            )[0]
        try:
            output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=78)
            return output.getvalue()
        finally:
            image.close()

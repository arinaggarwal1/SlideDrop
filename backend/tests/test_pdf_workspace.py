import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from main import MergePdfsRequest, merge_pdfs, pdf_preview
from converters.pdf_preview import render_preview


class PdfWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.sources = []
        for name, widths in [("first", [201, 202]), ("second", [301, 302])]:
            path = self.folder / f"{name}.pdf"
            writer = PdfWriter()
            for width in widths:
                writer.add_blank_page(width=width, height=400)
            writer.write(path)
            self.sources.append(str(path))

    def test_interleaved_order_duplicates_and_source_count(self):
        first, second = self.sources
        result = asyncio.run(merge_pdfs(MergePdfsRequest(
            files=[{"path": second, "page_range": "2"},
                   {"path": first, "page_range": "1"},
                   {"path": second, "page_range": "1"},
                   {"path": first, "page_range": "1"}],
            output_folder=str(self.folder), output_name="result.pdf",
        )))
        self.assertEqual([float(p.mediabox.width) for p in PdfReader(result.output_path).pages], [302, 201, 301, 201])
        self.assertEqual(result.source_count, 2)
        self.assertEqual(result.page_count, 4)
        self.assertEqual(len(PdfReader(first).pages), 2)

    def test_original_range_request(self):
        result = asyncio.run(merge_pdfs(MergePdfsRequest(
            files=[{"path": self.sources[0], "page_range": "1-2"}],
            output_folder=str(self.folder),
        )))
        self.assertEqual(result.page_count, 2)

    def test_preview_cache_and_invalid_page(self):
        render_preview.cache_clear()
        response = pdf_preview(self.sources[0], 1)
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertTrue(bytes(response.body).startswith(b"\xff\xd8"))
        pdf_preview(self.sources[0], 1)
        self.assertEqual(render_preview.cache_info().hits, 1)
        with self.assertRaises(HTTPException) as error:
            pdf_preview(self.sources[0], 3)
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()

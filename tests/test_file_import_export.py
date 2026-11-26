from io import BytesIO
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from backend.file_import import extract_zip, import_images
from backend.epub_export import export_epub


def png_bytes(color=(255, 255, 255)):
    image = Image.new("RGB", (8, 8), color)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class FileImportExportTests(unittest.TestCase):
    def test_zip_import_preserves_natural_page_order(self):
        with tempfile.TemporaryDirectory() as directory:
            stream = BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("pages/10.png", png_bytes((10, 0, 0)))
                archive.writestr("pages/2.png", png_bytes((2, 0, 0)))
                archive.writestr("pages/1.png", png_bytes((1, 0, 0)))
            result = extract_zip(stream.getvalue(), Path(directory), "chapter.zip")
            self.assertEqual(result["source_type"], "zip")
            self.assertEqual(result["count"], 3)
            self.assertEqual(
                [Path(page["source_member"]).name for page in result["pages"]],
                ["1.png", "2.png", "10.png"],
            )

    def test_zip_import_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            stream = BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("../escape.png", png_bytes())
            with self.assertRaisesRegex(ValueError, "unsafe"):
                extract_zip(stream.getvalue(), Path(directory), "bad.zip")

    def test_manual_images_can_be_added_incrementally(self):
        with tempfile.TemporaryDirectory() as directory:
            first = import_images([("page-1.png", png_bytes())], Path(directory))
            second = import_images([("page-2.png", png_bytes((0, 0, 0)))], Path(directory))
            self.assertEqual(first["count"], 1)
            self.assertEqual(second["count"], 1)
            self.assertTrue(Path(first["pages"][0]["image_path"]).is_file())
            self.assertTrue(Path(second["pages"][0]["image_path"]).is_file())

    def test_epub_export_creates_valid_package(self):
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "rendered.png"
            page.write_bytes(png_bytes())
            output = Path(directory) / "result.epub"
            result = export_epub(
                [{"index": 1, "image_path": str(page)}], str(output), "My Comic"
            )
            self.assertEqual(result["format"], "EPUB")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist()[0], "mimetype")
                self.assertEqual(archive.read("mimetype"), b"application/epub+zip")
                self.assertIn("OEBPS/content.opf", archive.namelist())
                self.assertIn("OEBPS/page-0001.xhtml", archive.namelist())


if __name__ == "__main__":
    unittest.main()

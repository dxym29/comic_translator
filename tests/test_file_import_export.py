from io import BytesIO
from pathlib import Path
import zipfile

import pytest
from PIL import Image

from backend.file_import import extract_zip, import_images
from backend.epub_export import export_epub


def png_bytes(color=(255, 255, 255)):
    image = Image.new("RGB", (8, 8), color)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_zip_import_preserves_natural_page_order(tmp_path):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("pages/10.png", png_bytes((10, 0, 0)))
        archive.writestr("pages/2.png", png_bytes((2, 0, 0)))
        archive.writestr("pages/1.png", png_bytes((1, 0, 0)))
    result = extract_zip(stream.getvalue(), tmp_path, "chapter.zip")
    assert result["source_type"] == "zip"
    assert result["count"] == 3
    assert [Path(page["source_member"]).name for page in result["pages"]] == ["1.png", "2.png", "10.png"]


def test_zip_import_rejects_path_traversal(tmp_path):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../escape.png", png_bytes())
    with pytest.raises(ValueError, match="unsafe"):
        extract_zip(stream.getvalue(), tmp_path, "bad.zip")


def test_manual_images_can_be_added_incrementally(tmp_path):
    first = import_images([("page-1.png", png_bytes())], tmp_path)
    second = import_images([("page-2.png", png_bytes((0, 0, 0)))], tmp_path)
    assert first["count"] == 1
    assert second["count"] == 1
    assert Path(first["pages"][0]["image_path"]).is_file()
    assert Path(second["pages"][0]["image_path"]).is_file()


def test_epub_export_creates_valid_package(tmp_path):
    page = tmp_path / "rendered.png"
    page.write_bytes(png_bytes())
    output = tmp_path / "result.epub"
    result = export_epub([{"index": 1, "image_path": str(page)}], str(output), "My Comic")
    assert result["format"] == "EPUB"
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.read("mimetype") == b"application/epub+zip"
        assert "OEBPS/content.opf" in archive.namelist()
        assert "OEBPS/page-0001.xhtml" in archive.namelist()

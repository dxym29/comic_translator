from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZIP_STORED
from typing import Any
import mimetypes
from datetime import datetime, timezone
from uuid import uuid4


def export_epub(pages: list[dict], output_path: str, title: str = "Comic Chapter") -> dict[str, Any]:
    files = []
    for page in pages:
        candidate = Path(str(page.get("image_path", ""))).expanduser()
        if candidate.is_file():
            files.append((int(page.get("index", len(files) + 1)), candidate))
    if not files:
        raise ValueError("EPUB export requires at least one existing rendered page.")
    files.sort(key=lambda item: item[0])
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe_title = escape(title or "Comic Chapter")
    identifier = "urn:uuid:" + str(uuid4())
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with ZipFile(destination, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        archive.writestr("META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            '</rootfiles></container>', compress_type=ZIP_DEFLATED)
        manifest = []
        spine = []
        nav = []
        for index, (number, path) in enumerate(files, 1):
            suffix = path.suffix.lower() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".png"
            image_name = f"images/page-{index:04d}{suffix}"
            page_name = f"page-{index:04d}.xhtml"
            media = mimetypes.guess_type(image_name)[0] or "image/png"
            archive.write(path, f"OEBPS/{image_name}", compress_type=ZIP_DEFLATED)
            archive.writestr(f"OEBPS/{page_name}",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page '
                + str(index) + '</title><meta name="viewport" content="width=device-width, initial-scale=1.0"/>'
                '<style>html,body{margin:0;padding:0}img{display:block;width:100%;height:auto}</style>'
                '</head><body><img src="' + escape(image_name) + '" alt="Page ' + str(index)
                + '"/></body></html>', compress_type=ZIP_DEFLATED)
            manifest.append(f'<item id="img{index}" href="{image_name}" media-type="{media}"/>')
            manifest.append(f'<item id="page{index}" href="{page_name}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="page{index}"/>')
            nav.append(f'<li><a href="{page_name}">Page {index}</a></li>')
        archive.writestr("OEBPS/nav.xhtml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            '<head><title>Contents</title></head><body><nav epub:type="toc"><ol>'
            + "".join(nav) + '</ol></nav></body></html>', compress_type=ZIP_DEFLATED)
        manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
        archive.writestr("OEBPS/content.opf",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:identifier id="bookid">' + identifier + '</dc:identifier>'
            '<dc:title>' + safe_title + '</dc:title><dc:language>my</dc:language>'
            '<meta property="dcterms:modified">' + modified + '</meta></metadata>'
            '<manifest>' + "".join(manifest) + '</manifest><spine>' + "".join(spine)
            + '</spine></package>', compress_type=ZIP_DEFLATED)
    return {"file_path": str(destination), "format": "EPUB", "page_count": len(files), "title": title}

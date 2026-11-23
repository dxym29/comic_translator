from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
from uuid import uuid4
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

MAX_EPUB_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_PAGE_BYTES = 100 * 1024 * 1024
MAX_PAGES = 2000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
XHTML_EXTENSIONS = {".xhtml", ".html", ".htm"}


class _ImageCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag.lower() == "img":
            src = values.get("src")
            if src:
                self.sources.append(src)
            srcset = values.get("srcset", "")
            if srcset:
                for candidate in srcset.split(","):
                    url = candidate.strip().split(" ")[0]
                    if url:
                        self.sources.append(url)
        if tag.lower() in {"image", "feimage"}:
            href = values.get("href") or values.get("{http://www.w3.org/1999/xlink}href")
            if href:
                self.sources.append(href)


def _safe_member(name: str) -> str:
    normalized = posixpath.normpath(name.replace("\\", "/"))
    if normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError("EPUB contains an unsafe archive path.")
    return normalized


def _resolve(base_dir: str, href: str) -> str:
    href = unquote(href.split("#", 1)[0].split("?", 1)[0])
    if not href:
        return ""
    if "://" in href or href.startswith(("data:", "/")):
        return ""
    return _safe_member(posixpath.join(base_dir, href))


def extract_epub(data: bytes, project_dir: Path, filename: str) -> dict:
    if not data:
        raise ValueError("The selected EPUB file is empty.")
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("The selected file is not a valid EPUB/ZIP archive.") from exc

    with archive:
        infos = archive.infolist()
        total_size = sum(info.file_size for info in infos)
        if total_size > MAX_EPUB_UNCOMPRESSED:
            raise ValueError("EPUB expands beyond the 1 GB safety limit.")
        names = set()
        for info in infos:
            safe = _safe_member(info.filename)
            if safe in names:
                continue
            names.add(safe)
            if info.file_size > MAX_PAGE_BYTES and Path(safe).suffix.lower() in IMAGE_EXTENSIONS:
                raise ValueError("EPUB contains an image larger than 100 MB.")

        if "META-INF/container.xml" not in names:
            raise ValueError("EPUB is missing META-INF/container.xml.")
        try:
            container_root = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(
                node for node in container_root.iter()
                if node.tag.rsplit("}", 1)[-1] == "rootfile"
            )
            opf_path = _safe_member(rootfile.attrib["full-path"])
            opf_root = ET.fromstring(archive.read(opf_path))
        except (ET.ParseError, KeyError, StopIteration) as exc:
            raise ValueError("EPUB package metadata (container.xml/OPF) is invalid.") from exc

        opf_dir = posixpath.dirname(opf_path)
        manifest: dict[str, tuple[str, str]] = {}
        spine_ids: list[str] = []
        title = Path(filename).stem
        for node in opf_root.iter():
            local = node.tag.rsplit("}", 1)[-1]
            if local == "item":
                item_id, href = node.attrib.get("id"), node.attrib.get("href")
                if item_id and href:
                    manifest[item_id] = (
                        _resolve(opf_dir, href),
                        node.attrib.get("media-type", "")
                    )
            elif local == "itemref":
                idref = node.attrib.get("idref")
                if idref:
                    spine_ids.append(idref)
            elif local == "title" and node.text and node.text.strip():
                title = node.text.strip()

        image_members: list[str] = []
        seen: set[str] = set()

        def add_image(member: str) -> None:
            if member and member in names and Path(member).suffix.lower() in IMAGE_EXTENSIONS and member not in seen:
                seen.add(member)
                image_members.append(member)
                if len(image_members) > MAX_PAGES:
                    raise ValueError("EPUB contains more than 2000 comic pages.")

        for item_id in spine_ids:
            member, media_type = manifest.get(item_id, ("", ""))
            if not member or member not in names:
                continue
            suffix = Path(member).suffix.lower()
            if suffix in IMAGE_EXTENSIONS or media_type.startswith("image/"):
                add_image(member)
                continue
            if suffix not in XHTML_EXTENSIONS and "html" not in media_type:
                continue
            try:
                parser = _ImageCollector()
                parser.feed(archive.read(member).decode("utf-8-sig", errors="replace"))
                base = posixpath.dirname(member)
                for href in parser.sources:
                    add_image(_resolve(base, href))
            except (KeyError, ValueError):
                continue

        # Some image-only EPUBs have no XHTML references; preserve manifest order as fallback.
        if not image_members:
            for member, media_type in manifest.values():
                if media_type.startswith("image/") or Path(member).suffix.lower() in IMAGE_EXTENSIONS:
                    add_image(member)

        if not image_members:
            raise ValueError("No supported manga page images were found in this EPUB.")
        import_folder = project_dir / "source" / "epub-imports" / uuid4().hex[:10]
        import_folder.mkdir(parents=True, exist_ok=False)
        pages = []
        from PIL import Image
        for index, member in enumerate(image_members, 1):
            raw = archive.read(member)
            if len(raw) > MAX_PAGE_BYTES:
                raise ValueError(f"EPUB page {index} is larger than 100 MB.")
            try:
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
            except Exception as exc:
                raise ValueError(f"EPUB page {index} is not a supported image: {member}") from exc
            suffix = Path(member).suffix.lower()
            destination = import_folder / f"page-{index:04d}{suffix}"
            destination.write_bytes(raw)
            pages.append({
                "index": index,
                "source_member": member,
                "image_path": str(destination)
            })

    return {
        "source_type": "epub",
        "source_filename": Path(filename).name,
        "title": title,
        "pages": pages,
        "count": len(pages),
        "note": "Pages were extracted in EPUB spine reading order where image references are available."
    }

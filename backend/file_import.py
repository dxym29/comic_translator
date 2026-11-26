from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import uuid4
from io import BytesIO
import zipfile
import re

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_IMAGE_BYTES = 100 * 1024 * 1024
MAX_PAGES = 2000


def _natural_key(value: str):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\\d+)", value)]


def _validate_image(raw: bytes, name: str) -> str:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image is empty or exceeds 100 MB: {name}")
    try:
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            image.verify()
            fmt = (image.format or "").lower()
    except Exception as exc:
        raise ValueError(f"Unsupported or damaged image: {name}") from exc
    return {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif", "bmp": ".bmp"}.get(fmt, Path(name).suffix.lower() or ".png")


def _save_pages(entries: list[tuple[str, bytes]], project_dir: Path, source_type: str, filename: str) -> dict:
    if not entries:
        raise ValueError("No supported comic images were found.")
    if len(entries) > MAX_PAGES:
        raise ValueError(f"Import contains more than {MAX_PAGES} images.")
    folder = project_dir / "source" / f"{source_type}-imports" / uuid4().hex[:10]
    folder.mkdir(parents=True, exist_ok=False)
    pages = []
    for index, (name, raw) in enumerate(entries, 1):
        suffix = _validate_image(raw, name)
        destination = folder / f"page-{index:04d}{suffix}"
        destination.write_bytes(raw)
        pages.append({"index": index, "source_member": name, "image_path": str(destination)})
    return {
        "source_type": source_type,
        "source_filename": Path(filename).name,
        "title": Path(filename).stem,
        "pages": pages,
        "count": len(pages),
        "note": "Images imported in archive order. Review the page order before processing."
    }


def extract_zip(data: bytes, project_dir: Path, filename: str) -> dict:
    if not data or len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("ZIP file is empty or exceeds the 500 MB upload limit.")
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("The selected file is not a valid ZIP archive.") from exc
    with archive:
        infos = []
        expanded = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("ZIP contains an unsafe file path.")
            expanded += info.file_size
            if expanded > MAX_EXPANDED_BYTES:
                raise ValueError("ZIP expands beyond the 1 GB safety limit.")
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                infos.append(info)
        infos.sort(key=lambda item: _natural_key(item.filename))
        if len(infos) > MAX_PAGES:
            raise ValueError(f"ZIP contains more than {MAX_PAGES} comic images.")
        entries = [(info.filename, archive.read(info)) for info in infos]
    return _save_pages(entries, project_dir, "zip", filename)


def import_images(files: list[tuple[str, bytes]], project_dir: Path, filename: str = "manual-images") -> dict:
    entries = []
    for name, raw in files:
        if Path(name).suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        entries.append((Path(name).name, raw))
    entries.sort(key=lambda item: _natural_key(item[0]))
    return _save_pages(entries, project_dir, "images", filename)

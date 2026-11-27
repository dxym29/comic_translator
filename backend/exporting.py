from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any


def export_chapter(
    pages: list[dict],
    output_path: str,
    title: str = "Comic Chapter",
    output_format: str | None = None,
) -> dict[str, Any]:
    requested = (output_format or Path(output_path).suffix.lstrip(".") or "zip").lower()
    if requested == "epub":
        from .epub_export import export_epub
        return export_epub(pages, output_path, title)
    if requested == "pdf":
        files = []
        for page in pages:
            candidate = Path(str(page.get("image_path", ""))).expanduser()
            if candidate.is_file():
                files.append((int(page.get("index", len(files) + 1)), candidate))
        if not files:
            raise ValueError("PDF export requires at least one existing rendered page.")
        files.sort(key=lambda item: item[0])
        images = []
        try:
            from PIL import Image
            for _, path in files:
                with Image.open(path) as source:
                    images.append(source.convert("RGB").copy())
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            images[0].save(destination, "PDF", save_all=True, append_images=images[1:], resolution=150.0)
            return {"file_path": str(destination), "format": "PDF", "page_count": len(images), "title": title}
        finally:
            for image in images:
                image.close()
    if requested not in {"zip", "cbz"}:
        raise ValueError("Export format must be EPUB, CBZ, ZIP or PDF.")
    files = []
    for page in pages:
        candidate = Path(str(page.get("image_path", ""))).expanduser()
        if candidate.is_file():
            files.append((int(page.get("index", len(files) + 1)), candidate))
    if not files:
        raise ValueError("export stage requires at least one existing rendered page")
    files.sort(key=lambda item: item[0])
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for number, path in files:
            archive.write(path, f"{number:04d}{path.suffix.lower() or '.png'}")
    return {"file_path": str(destination), "format": "CBZ" if requested == "cbz" else "ZIP",
            "page_count": len(files), "title": title}

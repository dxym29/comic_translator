from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any


def export_chapter(pages: list[dict], output_path: str, title: str = "Comic Chapter") -> dict[str, Any]:
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
    return {"file_path": str(destination), "format": "CBZ" if destination.suffix.lower() == ".cbz" else "ZIP",
            "page_count": len(files), "title": title}

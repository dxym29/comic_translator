from __future__ import annotations

from pathlib import Path
from typing import Any


FONT_FILES = {
    "Noto Sans Myanmar": ["NotoSansMyanmar-Regular.ttf", "NotoSansMyanmar-VF.ttf"],
    "Pyidaungsu": ["Pyidaungsu.ttf", "Pyidaungsu Book.ttf"],
    "Padauk": ["Padauk-Regular.ttf", "Padauk.ttf"],
}


def _font_path(name: str) -> str | None:
    """Find a font file when needed; installed Windows fonts may have variable filenames."""
    candidates = FONT_FILES.get(name, FONT_FILES["Noto Sans Myanmar"])
    roots = [
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for candidate in candidates:
            found = next((p for p in root.rglob("*") if p.is_file() and p.name.casefold() == candidate.casefold()), None)
            if found:
                return str(found)
        if name.casefold() == "noto sans myanmar":
            found = next((p for p in root.rglob("*") if p.is_file() and
                          p.suffix.casefold() in {".ttf", ".otf", ".ttc"} and
                          "noto" in p.name.casefold() and "myanmar" in p.name.casefold()), None)
            if found:
                return str(found)
    return None


def _installed_family(name: str, database) -> str | None:
    """Match installed family names independently of the font file's filename."""
    wanted = " ".join(name.casefold().replace("-", " ").split())
    for family in database.families():
        normalized = " ".join(family.casefold().replace("-", " ").split())
        if normalized == wanted:
            return family
    aliases = {
        "noto sans myanmar": ("noto sans myanmar", "noto sans myanmar ui"),
        "pyidaungsu": ("pyidaungsu",),
        "padauk": ("padauk",),
    }
    for family in database.families():
        normalized = " ".join(family.casefold().replace("-", " ").split())
        if any(alias in normalized for alias in aliases.get(wanted, (wanted,))):
            return family
    return None


def initialize_text_renderer():
    """Create Qt's text engine on the API main thread; Qt uses HarfBuzz for Myanmar shaping."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


def render_page(image_path: str, regions: list[dict], output_path: str,
                font_family: str = "Noto Sans Myanmar", style: str = "original_bubble",
                font_size: int = 42, text_color: str = "#171717",
                outline_color: str = "#ffffff") -> dict[str, Any]:
    source = Path(image_path)
    if not source.is_file():
        raise ValueError("typeset stage requires a valid cleaned image_path")

    try:
        from PIL import Image
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import (
            QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPen,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Myanmar text rendering requires the Qt text engine. "
            "Run: python -m backend.repair_local_env"
        ) from exc

    initialize_text_renderer()
    # First use Windows/Qt's installed system font database. This handles
    # per-user installs and variable-font filenames that do not match a
    # hard-coded .ttf filename.
    installed = _installed_family(font_family, QFontDatabase)
    font_file = _font_path(font_family)
    if installed:
        family_name = installed
        font_source = "Windows installed font"
    elif font_file:
        font_id = QFontDatabase.addApplicationFont(font_file)
        if font_id < 0:
            raise RuntimeError(f"Could not load font file: {font_file}")
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            raise RuntimeError(f"Could not read the font family from: {font_file}")
        family_name = families[0]
        font_source = font_file
    else:
        raise RuntimeError(
            f"{font_family} font was not found in Qt's installed font list or Windows font folders. "
            "Check that Windows Settings > Personalization > Fonts shows this font, then restart Comic Translator."
        )

    with Image.open(source) as opened:
        rgb = opened.convert("RGB")
        width, height = rgb.size
        raw = rgb.tobytes()
    qimage = QImage(raw, width, height, width * 3, QImage.Format.Format_RGB888).copy()
    painter = QPainter(qimage)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    flags = (
        int(Qt.AlignmentFlag.AlignHCenter)
        | int(Qt.AlignmentFlag.AlignVCenter)
        | int(Qt.TextFlag.TextWordWrap)
        | int(Qt.TextFlag.TextWrapAnywhere)
    )
    rendered = 0

    # Accept grouped balloon regions; combine legacy line-level translations by bubble_id.
    grouped: dict[str, dict] = {}
    for index, item in enumerate(sorted(regions, key=lambda r: int(r.get("reading_order", 0)))):
        text = str(item.get("translated_text", item.get("translation", ""))).strip()
        if not text:
            continue
        group_id = str(item.get("bubble_id") or item.get("id") or f"region-{index}")
        if group_id not in grouped:
            grouped[group_id] = dict(item)
            grouped[group_id]["translated_text"] = text
            grouped[group_id]["x"] = int(item.get("bubble_x", item.get("x", 0)))
            grouped[group_id]["y"] = int(item.get("bubble_y", item.get("y", 0)))
            grouped[group_id]["width"] = int(item.get("bubble_width", item.get("width", 0)))
            grouped[group_id]["height"] = int(item.get("bubble_height", item.get("height", 0)))
        elif item.get("bubble_id"):
            grouped[group_id]["translated_text"] += " " + text

    for item in sorted(grouped.values(), key=lambda r: int(r.get("reading_order", 0))):
        text = str(item.get("translated_text", "")).strip()
        if not text:
            continue
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        w = int(item.get("width", 0))
        h = int(item.get("height", 0))
        if w < 4 or h < 4 or x < 0 or y < 0 or x + w > width or y + h > height:
            continue

        inset = max(3, min(w, h) // 14)
        rect = QRectF(x + inset, y + inset, max(1, w - inset * 2), max(1, h - inset * 2))
        chosen = None
        # Start larger and shrink only as much as needed; avoid unreadable 8px text.
        for size in range(max(16, int(font_size)), 13, -1):
            font = QFont(family_name)
            font.setPixelSize(size)
            metrics = QFontMetricsF(font)
            bounds = metrics.boundingRect(rect, int(flags), text)
            if bounds.width() <= rect.width() + 1 and bounds.height() <= rect.height() + 1:
                chosen = font
                break
        if chosen is None:
            chosen = QFont(family_name)
            chosen.setPixelSize(14)

        painter.setFont(chosen)
        if style == "professional":
            painter.setPen(QPen(QColor(outline_color), 2))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (1, 1), (-1, 1), (1, -1)):
                painter.drawText(rect.translated(dx, dy), int(flags), text)
        painter.setPen(QPen(QColor(text_color)))
        painter.drawText(rect, int(flags), text)
        rendered += 1

    painter.end()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not qimage.save(str(target), "PNG"):
        raise RuntimeError(f"Could not save rendered page: {target}")

    return {
        "image_path": str(target),
        "rendered_regions": rendered,
        "font_family": family_name,
        "font_path": font_source,
        "raqm_available": False,
        "text_layout": "Qt HarfBuzz",
    }

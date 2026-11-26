from __future__ import annotations

from pathlib import Path
from typing import Any


FONT_FILES = {
    "Noto Sans Myanmar": ["NotoSansMyanmar-Regular.ttf", "NotoSansMyanmar-VF.ttf"],
    "Pyidaungsu": ["Pyidaungsu.ttf", "Pyidaungsu Book.ttf"],
    "Padauk": ["Padauk-Regular.ttf", "Padauk.ttf"],
}


def _font_path(name: str) -> str:
    candidates = FONT_FILES.get(name, FONT_FILES["Noto Sans Myanmar"])
    roots = [
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path("/usr/share/fonts/truetype"),
        Path("/usr/local/share/fonts"),
    ]
    for root in roots:
        for candidate in candidates:
            found = list(root.rglob(candidate)) if root.exists() else []
            if found:
                return str(found[0])
    raise RuntimeError(
        f"{name} font was not found. Install the font in Windows, then restart Comic Translator."
    )


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
                font_size: int = 30, text_color: str = "#171717",
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
    font_file = _font_path(font_family)
    font_id = QFontDatabase.addApplicationFont(font_file)
    if font_id < 0:
        raise RuntimeError(f"Could not load font file: {font_file}")
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError(f"Could not read the font family from: {font_file}")

    with Image.open(source) as opened:
        rgb = opened.convert("RGB")
        width, height = rgb.size
        raw = rgb.tobytes()
    qimage = QImage(raw, width, height, width * 3, QImage.Format.Format_RGB888).copy()
    painter = QPainter(qimage)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    flags = (
        Qt.AlignmentFlag.AlignHCenter
        | Qt.AlignmentFlag.AlignVCenter
        | Qt.TextFlag.TextWordWrap
        | Qt.TextFlag.TextWrapAnywhere
    )
    rendered = 0

    for item in sorted(regions, key=lambda r: int(r.get("reading_order", 0))):
        text = str(item.get("translated_text", item.get("translation", ""))).strip()
        if not text:
            continue

        x = int(item.get("bubble_x", item.get("x", 0)))
        y = int(item.get("bubble_y", item.get("y", 0)))
        w = int(item.get("bubble_width", item.get("width", 0)))
        h = int(item.get("bubble_height", item.get("height", 0)))
        if w < 4 or h < 4 or x < 0 or y < 0 or x + w > width or y + h > height:
            continue

        inset = max(2, min(w, h) // 18)
        rect = QRectF(x + inset, y + inset, max(1, w - inset * 2), max(1, h - inset * 2))
        chosen = None
        for size in range(max(8, int(font_size)), 7, -1):
            font = QFont(families[0])
            font.setPixelSize(size)
            metrics = QFontMetricsF(font)
            bounds = metrics.boundingRect(rect, int(flags), text)
            if bounds.width() <= rect.width() + 1 and bounds.height() <= rect.height() + 1:
                chosen = font
                break
        if chosen is None:
            chosen = QFont(families[0])
            chosen.setPixelSize(8)

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
        "font_family": families[0],
        "font_path": font_file,
        "raqm_available": False,
        "text_layout": "Qt HarfBuzz",
    }

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, features


FONT_FILES = {
    "Noto Sans Myanmar": ["NotoSansMyanmar-Regular.ttf", "NotoSansMyanmar-VF.ttf"],
    "Pyidaungsu": ["Pyidaungsu.ttf", "Pyidaungsu Book.ttf"],
    "Padauk": ["Padauk-Regular.ttf", "Padauk.ttf"],
}


def _font_path(name: str) -> str:
    candidates = FONT_FILES.get(name, FONT_FILES["Noto Sans Myanmar"])
    roots = [Path("C:/Windows/Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
             Path("/usr/share/fonts/truetype"), Path("/usr/local/share/fonts")]
    for root in roots:
        for candidate in candidates:
            found = list(root.rglob(candidate)) if root.exists() else []
            if found:
                return str(found[0])
    raise RuntimeError(
        f"{name} font was not found. Install the font in Windows, then restart Comic Translator."
    )


def _wrap(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> str:
    words = text.split()
    if not words:
        return text
    lines, current = [], ""
    for word in words:
        trial = word if not current else current + " " + word
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    # Myanmar text often has no spaces; split long unbroken strings by character.
    output = []
    for line in lines:
        if draw.textbbox((0, 0), line, font=font)[2] <= max_width:
            output.append(line)
            continue
        part = ""
        for char in line:
            trial = part + char
            if part and draw.textbbox((0, 0), trial, font=font)[2] > max_width:
                output.append(part)
                part = char
            else:
                part = trial
        if part:
            output.append(part)
    return "\n".join(output)


def render_page(image_path: str, regions: list[dict], output_path: str,
                font_family: str = "Noto Sans Myanmar", style: str = "original_bubble",
                font_size: int = 30, text_color: str = "#171717",
                outline_color: str = "#ffffff") -> dict[str, Any]:
    source = Path(image_path)
    if not source.is_file():
        raise ValueError("typeset stage requires a valid cleaned image_path")
    # Prefer RAQM for correct Myanmar shaping. Some Windows/Python builds
    # ship Pillow without libraqm; allow a BASIC fallback so the pipeline can
    # complete, and expose the limitation in the stage result.
    raqm_available = bool(features.check("raqm"))
    layout_engine = ImageFont.Layout.RAQM if raqm_available else ImageFont.Layout.BASIC
    font_path = _font_path(font_family)
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    rendered = 0
    for item in sorted(regions, key=lambda r: int(r.get("reading_order", 0))):
        text = str(item.get("translated_text", item.get("translation", ""))).strip()
        if not text:
            continue
        x = int(item.get("bubble_x", item.get("x", 0)))
        y = int(item.get("bubble_y", item.get("y", 0)))
        w = int(item.get("bubble_width", item.get("width", 0)))
        h = int(item.get("bubble_height", item.get("height", 0)))
        if w < 4 or h < 4 or x < 0 or y < 0 or x + w > image.width or y + h > image.height:
            continue
        # Keep a small inset from the detected bubble/text box.
        inset = max(2, min(w, h) // 18)
        max_w, max_h = max(1, w - inset * 2), max(1, h - inset * 2)
        chosen, wrapped = None, text
        for size in range(max(8, int(font_size)), 7, -1):
            font = ImageFont.truetype(font_path, size, layout_engine=layout_engine)
            candidate = _wrap(text, font, draw, max_w)
            box = draw.multiline_textbbox((0, 0), candidate, font=font, spacing=max(1, size // 6),
                                          align="center", stroke_width=0)
            if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
                chosen, wrapped = font, candidate
                break
        if chosen is None:
            chosen = ImageFont.truetype(font_path, 8, layout_engine=layout_engine)
            wrapped = _wrap(text, chosen, draw, max_w)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=chosen, spacing=2, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px = x + max(0, (w - tw) // 2) - bbox[0]
        py = y + max(0, (h - th) // 2) - bbox[1]
        stroke = 1 if style == "professional" else 0
        draw.multiline_text((px, py), wrapped, font=chosen, fill=text_color, spacing=2,
                            align="center", stroke_width=stroke, stroke_fill=outline_color)
        rendered += 1
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True)
    return {"image_path": str(target), "rendered_regions": rendered,
            "font_family": font_family, "font_path": font_path,
            "raqm_available": raqm_available,\n            "warning": "" if raqm_available else "Pillow has no libraqm; basic text layout was used and Myanmar shaping may be imperfect. Install a Pillow build with libraqm for best results."}

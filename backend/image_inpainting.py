from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .image_cleanup import build_text_mask


def inpaint_with_lama(image_path: str, regions: list[dict], output_path: str,
                      padding_ratio: float = 0.18) -> dict[str, Any]:
    """Run the CPU-capable LaMa model through simple-lama-inpainting.

    Install the optional CPU stack from backend/requirements-lama-cpu.txt.
    Model weights are downloaded by the package on first use.
    """
    source = Path(image_path).expanduser()
    if not source.is_file():
        raise ValueError("remove stage requires a valid image_path")
    if not regions:
        raise ValueError("remove stage requires reviewed text regions")
    try:
        from simple_lama_inpainting import SimpleLama
    except ImportError as exc:
        raise RuntimeError(
            "LaMa AI inpainting is not installed. Run: "
            "pip install -r backend/requirements-lama-cpu.txt"
        ) from exc
    with Image.open(source) as opened:
        rgb = opened.convert("RGB")
    image = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    mask = build_text_mask(image.shape, regions, padding_ratio=padding_ratio)
    if not np.any(mask):
        raise ValueError("No valid mask pixels. Check the edited text-region coordinates.")
    mask_image = Image.fromarray(mask).convert("L")
    # Lazy model initialization keeps app startup light on CPU-only machines.
    lama = SimpleLama()
    result = lama(rgb, mask_image)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.save(destination, format="PNG")
    return {"image_path": str(destination), "mask_path": "", "engine": "LaMa",
            "model": "simple-lama-inpainting", "width": rgb.width, "height": rgb.height}

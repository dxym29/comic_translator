from __future__ import annotations

import cv2
import numpy as np


def build_text_mask(
    image_shape: tuple[int, ...],
    regions: list[dict],
    padding_ratio: float = 0.18,
) -> np.ndarray:
    height, width = image_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("width", 0))
        h = int(region.get("height", 0))
        if w <= 0 or h <= 0:
            continue
        pad_x = max(2, int(w * padding_ratio))
        pad_y = max(2, int(h * padding_ratio))
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(width, x + w + pad_x), min(height, y + h + pad_y)
        if x2 > x1 and y2 > y1:
            cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
    return mask


def remove_text(
    image: np.ndarray,
    regions: list[dict],
    inpaint_radius: float = 3.0,
    padding_ratio: float = 0.18,
) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("The source image is empty.")
    if not regions:
        return image.copy()
    mask = build_text_mask(image.shape, regions, padding_ratio=padding_ratio)
    if not np.any(mask):
        return image.copy()
    return cv2.inpaint(image, mask, inpaint_radius, cv2.INPAINT_TELEA)

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np


@lru_cache(maxsize=2)
def _build_engine(language: str):
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Install backend/requirements-ocr-cpu.txt first."
        ) from exc

    return PaddleOCR(
        lang=language,
        ocr_version="PP-OCRv5",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
    )


def _result_payload(result: Any) -> dict:
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if payload is None and isinstance(result, dict):
        payload = result
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def _box_from_polygon(polygon: Any) -> tuple[int, int, int, int] | None:
    points = np.asarray(polygon, dtype=float).reshape(-1, 2)
    if points.size == 0:
        return None
    x1 = max(0, int(np.floor(points[:, 0].min())))
    y1 = max(0, int(np.floor(points[:, 1].min())))
    x2 = max(x1 + 1, int(np.ceil(points[:, 0].max())))
    y2 = max(y1 + 1, int(np.ceil(points[:, 1].max())))
    return x1, y1, x2 - x1, y2 - y1


def recognize_image(image: np.ndarray, language: str = "en") -> list[dict]:
    if image is None or image.size == 0:
        raise ValueError("The uploaded image is empty.")
    if language not in {"en", "ch", "japan", "korean", "th"}:
        raise ValueError("Unsupported OCR language selection.")

    engine = _build_engine(language)
    results = engine.predict(image)
    regions: list[dict] = []
    for page in results or []:
        payload = _result_payload(page)
        polygons = payload.get("dt_polys") or []
        texts = payload.get("rec_texts") or []
        scores = payload.get("rec_scores") or []
        boxes = payload.get("rec_boxes") or []

        count = max(len(polygons), len(boxes), len(texts))
        for index in range(count):
            box = None
            if index < len(polygons):
                box = _box_from_polygon(polygons[index])
            elif index < len(boxes):
                raw = np.asarray(boxes[index]).reshape(-1)
                if raw.size >= 4:
                    x1, y1, x2, y2 = [int(value) for value in raw[:4]]
                    box = (max(0, x1), max(0, y1), max(1, x2 - x1), max(1, y2 - y1))
            if box is None:
                continue
            text = str(texts[index]) if index < len(texts) else ""
            try:
                confidence = float(scores[index]) if index < len(scores) else None
            except (TypeError, ValueError):
                confidence = None
            regions.append({
                "index": len(regions),
                "x": box[0], "y": box[1],
                "width": box[2], "height": box[3],
                "text": text,
                "confidence": confidence,
                "status": "detected",
            })
    return regions

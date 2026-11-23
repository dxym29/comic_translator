from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np


_LANGUAGE_ALIASES = {
    "english": "en", "en": "en",
    "japanese": "japan", "japan": "japan", "ja": "japan",
    "chinese": "ch", "ch": "ch",
    "korean": "korean", "ko": "korean",
    "thai": "th", "th": "th",
    "other": "en",
}
_PP_OCRV6_LANGUAGES = {"en", "japan", "ch"}


def normalize_language(language: str | None) -> str:
    key = str(language or "en").strip().lower()
    try:
        return _LANGUAGE_ALIASES[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported OCR language: {language}") from exc


def model_label(language: str | None = "en") -> str:
    lang = normalize_language(language)
    version = "PP-OCRv6" if lang in _PP_OCRV6_LANGUAGES else "PP-OCRv5"
    return f"{version} · ONNX Runtime CPU · {lang}"


@lru_cache(maxsize=5)
def _build_engine(language: str):
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Run: pip install -r backend/requirements-ocr-cpu.txt"
        ) from exc
    try:
        import onnxruntime  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "ONNX Runtime is not installed. Run: pip install -r backend/requirements-ocr-cpu.txt"
        ) from exc

    version = "PP-OCRv6" if language in _PP_OCRV6_LANGUAGES else "PP-OCRv5"
    try:
        return PaddleOCR(
            lang=language,
            ocr_version=version,
            engine="onnxruntime",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not initialize {version} for '{language}' with ONNX Runtime CPU: {exc}"
        ) from exc


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


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        return value.tolist()
    return list(value)


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
    lang = normalize_language(language)
    engine = _build_engine(lang)
    results = engine.predict(image)
    regions: list[dict] = []

    for page in results or []:
        payload = _result_payload(page)
        polygons = _as_list(payload.get("rec_polys")) or _as_list(payload.get("dt_polys"))
        texts = _as_list(payload.get("rec_texts"))
        scores = _as_list(payload.get("rec_scores"))
        boxes = _as_list(payload.get("rec_boxes"))

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
            text = str(texts[index]).strip() if index < len(texts) else ""
            if not text:
                continue
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
                "reading_order": 0,
                "kind": "speech",
                "status": "detected",
            })

    # Stable top-to-bottom, then left-to-right order for English reading flow.
    regions.sort(key=lambda item: (item["y"] + item["height"] / 2, item["x"]))
    for index, region in enumerate(regions):
        region["index"] = index
        region["reading_order"] = index + 1
    return regions

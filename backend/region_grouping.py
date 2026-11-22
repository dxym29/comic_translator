from __future__ import annotations

from statistics import median
from typing import Any


def _overlap_ratio(a: dict, b: dict) -> float:
    left = max(a["x"], b["x"])
    right = min(a["x"] + a["width"], b["x"] + b["width"])
    overlap = max(0, right - left)
    denominator = max(1, min(a["width"], b["width"]))
    return overlap / denominator


def group_text_regions(regions: list[dict]) -> list[dict]:
    """Conservatively suggest multi-line text blocks; never discard source regions."""
    valid = []
    for index, region in enumerate(regions):
        try:
            x, y = int(region["x"]), int(region["y"])
            width, height = int(region["width"]), int(region["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        valid.append({
            "source_index": int(region.get("index", index)),
            "x": x, "y": y, "width": width, "height": height,
            "text": str(region.get("text", "") or ""),
            "confidence": region.get("confidence"),
        })

    if not valid:
        return []

    typical_height = median(item["height"] for item in valid)
    max_vertical_gap = max(8, int(typical_height * 1.35))
    parent = list(range(len(valid)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    # Pairwise grouping is cheap for typical comic pages (usually well below 300 lines).
    for i, first in enumerate(valid):
        for j in range(i + 1, len(valid)):
            second = valid[j]
            top, bottom = (first, second) if first["y"] <= second["y"] else (second, first)
            vertical_gap = bottom["y"] - (top["y"] + top["height"])
            if vertical_gap < -min(top["height"], bottom["height"]) * 0.35:
                continue
            if vertical_gap > max_vertical_gap:
                continue
            horizontal_overlap = _overlap_ratio(first, second)
            center_distance = abs(
                (first["x"] + first["width"] / 2)
                - (second["x"] + second["width"] / 2)
            )
            narrower_width = min(first["width"], second["width"])
            aligned_centers = center_distance <= max(10, narrower_width * 0.28)
            if horizontal_overlap >= 0.58 or (horizontal_overlap >= 0.35 and aligned_centers):
                union(i, j)

    clusters: dict[int, list[dict[str, Any]]] = {}
    for index, region in enumerate(valid):
        clusters.setdefault(find(index), []).append(region)

    groups = []
    for members in clusters.values():
        members.sort(key=lambda item: (item["y"], item["x"]))
        x1 = min(item["x"] for item in members)
        y1 = min(item["y"] for item in members)
        x2 = max(item["x"] + item["width"] for item in members)
        y2 = max(item["y"] + item["height"] for item in members)
        groups.append({
            "group_index": len(groups),
            "region_indices": [item["source_index"] for item in members],
            "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1,
            "text": "\n".join(item["text"] for item in members if item["text"]),
            "line_count": len(members),
            "confidence": (
                sum(float(item["confidence"]) for item in members if item["confidence"] is not None)
                / sum(1 for item in members if item["confidence"] is not None)
                if any(item["confidence"] is not None for item in members) else None
            ),
        })

    groups.sort(key=lambda item: (item["y"], item["x"]))
    for index, group in enumerate(groups):
        group["group_index"] = index
    return groups

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import cv2
import numpy as np
from PIL import Image

from .image_cleanup import build_text_mask
from .storage import get_data_dir


MODEL_SPECS = {
    "lama_manga": {
        "label": "LaMa Manga",
        "filename": "anime-manga-big-lama.pt",
        "url": "https://github.com/Sanster/models/releases/download/AnimeMangaInpainting/anime-manga-big-lama.pt",
        "md5": "29f284f36a0a510bcacf39ecf4c4d54f",
        "pad": 8,
    },
    "aot_gan": {
        "label": "AOT-GAN Manga/Anime",
        "filename": "aot_traced.pt",
        "url": "https://huggingface.co/ogkalu/aot-inpainting/resolve/42ffc84ff1bd46dd95f1c5a41e83ee7e98f39189/aot_traced.pt",
        "md5": "82350e9ce753fbdf59bc9250bcf4dd73",
        "pad": 4,
    },
}

_MODEL_CACHE: dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()


def _model_path(model_name: str) -> Path:
    if model_name not in MODEL_SPECS:
        raise ValueError(f"Unknown inpainting model: {model_name}. Choose lama_manga or aot_gan.")
    folder = get_data_dir() / "models" / "inpainting"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / MODEL_SPECS[model_name]["filename"]


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_model(model_name: str) -> Path:
    spec = MODEL_SPECS[model_name]
    path = _model_path(model_name)
    if path.is_file() and _md5(path) == spec["md5"]:
        return path
    if path.exists():
        path.unlink()
    request = Request(spec["url"], headers={"User-Agent": "ComicTranslator/1.0"})
    temporary = path.with_suffix(path.suffix + ".download")
    try:
        with urlopen(request, timeout=45) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        actual = _md5(temporary)
        if actual != spec["md5"]:
            raise RuntimeError(
                f"{spec['label']} model checksum mismatch. Expected {spec['md5']}, got {actual}."
            )
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def _load_model(model_name: str):
    with _MODEL_LOCK:
        if model_name in _MODEL_CACHE:
            return _MODEL_CACHE[model_name]
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("PyTorch CPU is required. Install backend/requirements-lama-cpu.txt first.") from exc
        path = _ensure_model(model_name)
        try:
            torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
            model = torch.jit.load(str(path), map_location="cpu")
            model.eval()
        except Exception as exc:
            raise RuntimeError(f"Could not load {MODEL_SPECS[model_name]['label']} weights: {exc}") from exc
        _MODEL_CACHE[model_name] = model
        return model


def _pad_to_multiple(array: np.ndarray, multiple: int) -> tuple[np.ndarray, tuple[int, int]]:
    height, width = array.shape[:2]
    padded_h = ((height + multiple - 1) // multiple) * multiple
    padded_w = ((width + multiple - 1) // multiple) * multiple
    pad_h, pad_w = padded_h - height, padded_w - width
    if array.ndim == 2:
        padded = np.pad(array, ((0, pad_h), (0, pad_w)), mode="symmetric")
    else:
        padded = np.pad(array, ((0, pad_h), (0, pad_w), (0, 0)), mode="symmetric")
    return padded, (height, width)


def _run_lama_manga(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    import torch
    model = _load_model("lama_manga")
    image_pad, original_size = _pad_to_multiple(rgb, 8)
    mask_pad, _ = _pad_to_multiple(mask, 8)
    image_tensor = torch.from_numpy(image_pad.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    mask_tensor = torch.from_numpy((mask_pad > 0).astype(np.float32)).unsqueeze(0).unsqueeze(0)
    with torch.inference_mode():
        output = model(image_tensor, mask_tensor)
    result = output[0].permute(1, 2, 0).cpu().numpy()
    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
    height, width = original_size
    result = result[:height, :width]
    result[mask == 0] = rgb[mask == 0]
    return result


def _run_aot_gan(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    import torch
    model = _load_model("aot_gan")
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    image_pad, original_size = _pad_to_multiple(bgr, 4)
    mask_pad, _ = _pad_to_multiple(mask, 4)
    image_tensor = torch.from_numpy(np.ascontiguousarray(image_pad)).permute(2, 0, 1).unsqueeze(0).float()
    image_tensor = image_tensor / 127.5 - 1.0
    mask_tensor = torch.from_numpy(np.ascontiguousarray(mask_pad)).unsqueeze(0).unsqueeze(0)
    mask_tensor = (mask_tensor > 127).to(image_tensor.dtype)
    image_tensor = image_tensor * (1.0 - mask_tensor)
    with torch.inference_mode():
        output = model(image_tensor, mask_tensor)
    result = output[0].permute(1, 2, 0).float().cpu().numpy()
    result = np.clip((result + 1.0) * 127.5, 0, 255).astype(np.uint8)
    height, width = original_size
    result = cv2.cvtColor(result[:height, :width], cv2.COLOR_BGR2RGB)
    result[mask == 0] = rgb[mask == 0]
    return result


def inpaint_with_model(image_path: str, regions: list[dict], output_path: str,
                       padding_ratio: float = 0.18, model_name: str = "lama_manga") -> dict[str, Any]:
    source = Path(image_path).expanduser()
    if not source.is_file():
        raise ValueError("remove stage requires a valid image_path")
    if not regions:
        raise ValueError("remove stage requires reviewed text regions")
    if model_name not in MODEL_SPECS:
        raise ValueError("Select either LaMa Manga or AOT-GAN Manga/Anime.")
    with Image.open(source) as opened:
        rgb = np.asarray(opened.convert("RGB"))
    image_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    mask = build_text_mask(image_bgr.shape, regions, padding_ratio=padding_ratio)
    if not np.any(mask):
        raise ValueError("No valid mask pixels. Check the edited text-region coordinates.")
    if model_name == "lama_manga":
        result = _run_lama_manga(rgb, mask)
    else:
        result = _run_aot_gan(rgb, mask)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result).save(destination, format="PNG")
    spec = MODEL_SPECS[model_name]
    return {
        "image_path": str(destination),
        "mask_path": "",
        "engine": spec["label"],
        "model": model_name,
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
    }


def inpaint_with_lama(image_path: str, regions: list[dict], output_path: str,
                      padding_ratio: float = 0.18) -> dict[str, Any]:
    """Backward-compatible alias for the manga-finetuned LaMa engine."""
    return inpaint_with_model(image_path, regions, output_path, padding_ratio, "lama_manga")

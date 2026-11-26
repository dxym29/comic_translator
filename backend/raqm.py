from __future__ import annotations

import hashlib
import os
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
import zstandard

from .storage import get_data_dir

# Official MSYS2 UCRT64 FriBiDi package. SHA-256 is pinned.
_PACKAGE_URL = (
    "https://mirror.msys2.org/mingw/ucrt64/"
    "mingw-w64-ucrt-x86_64-fribidi-1.0.18-1-any.pkg.tar.zst"
)
_PACKAGE_SHA256 = "4837d3626349c617aaa2db3d116f9b7ea208b11644f507a6a83eab36bb3ac920"
_DLL_NAME = "libfribidi-0.dll"
_DLL_DIR = get_data_dir() / "runtime" / "raqm"
_DLL_PATH = _DLL_DIR / _DLL_NAME
_INSTALL_MARKER = _DLL_DIR / ".fribidi-package-installed"
_DLL_DIRECTORY_HANDLE: Any = None


def _install_fribidi_package() -> None:
    _DLL_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(_PACKAGE_URL, timeout=60)
    response.raise_for_status()
    package = response.content
    digest = hashlib.sha256(package).hexdigest()
    if digest != _PACKAGE_SHA256:
        raise RuntimeError(
            "FriBiDi download checksum mismatch. The runtime DLLs were not installed."
        )

    extracted = set()
    try:
        reader = zstandard.ZstdDecompressor().stream_reader(BytesIO(package))
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                normalized = member.name.replace("\\\\", "/")
                if "/bin/" not in normalized or not normalized.lower().endswith(".dll"):
                    continue
                source = archive.extractfile(member)
                if source is None:
                    continue
                # Keep the official package's DLL dependencies together so
                # Windows can resolve FriBiDi's dependent runtime libraries.
                filename = Path(normalized).name
                data = source.read()
                if filename.lower() == _DLL_NAME.lower() and not data.startswith(b"MZ"):
                    raise RuntimeError("Downloaded FriBiDi file is not a valid Windows DLL.")
                temporary = _DLL_DIR / (filename + ".tmp")
                temporary.write_bytes(data)
                temporary.replace(_DLL_DIR / filename)
                extracted.add(filename.lower())
    except Exception:
        _DLL_PATH.unlink(missing_ok=True)
        _INSTALL_MARKER.unlink(missing_ok=True)
        raise

    if _DLL_NAME.lower() not in extracted or not _DLL_PATH.is_file():
        raise RuntimeError("FriBiDi DLL was not found inside the verified MSYS2 package.")
    _INSTALL_MARKER.write_text("verified MSYS2 FriBiDi package\\n", encoding="utf-8")


def ensure_raqm() -> Path | None:
    """Ensure Pillow can load RAQM. On Windows, install FriBiDi and its DLL dependencies."""
    global _DLL_DIRECTORY_HANDLE

    if os.name == "nt":
        # Reinstall when the marker is absent (including older installs that
        # only extracted FriBiDi but omitted its dependent runtime DLLs).
        if not _INSTALL_MARKER.is_file() or not _DLL_PATH.is_file():
            _install_fribidi_package()

        if _DLL_DIRECTORY_HANDLE is None:
            _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(_DLL_DIR))
        return _DLL_PATH

    return None

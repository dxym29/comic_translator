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

# Official MSYS2 UCRT64 FriBiDi package. SHA-256 is pinned to prevent
# downloading or loading an unexpected DLL.
_PACKAGE_URL = (
    "https://mirror.msys2.org/mingw/ucrt64/"
    "mingw-w64-ucrt-x86_64-fribidi-1.0.18-1-any.pkg.tar.zst"
)
_PACKAGE_SHA256 = "4837d3626349c617aaa2db3d116f9b7ea208b11644f507a6a83eab36bb3ac920"
_DLL_NAME = "libfribidi-0.dll"
_DLL_DIR = get_data_dir() / "runtime" / "raqm"
_DLL_PATH = _DLL_DIR / _DLL_NAME
_DLL_DIRECTORY_HANDLE: Any = None


def ensure_raqm() -> Path | None:
    """Ensure Pillow can load RAQM. On Windows, install the pinned FriBiDi DLL."""
    global _DLL_DIRECTORY_HANDLE

    if os.name == "nt":
        if not _DLL_PATH.is_file():
            _DLL_DIR.mkdir(parents=True, exist_ok=True)
            response = requests.get(_PACKAGE_URL, timeout=60)
            response.raise_for_status()
            package = response.content
            digest = hashlib.sha256(package).hexdigest()
            if digest != _PACKAGE_SHA256:
                raise RuntimeError(
                    "FriBiDi download checksum mismatch. The runtime DLL was not installed."
                )
            try:
                reader = zstandard.ZstdDecompressor().stream_reader(BytesIO(package))
                with tarfile.open(fileobj=reader, mode="r|") as archive:
                    for member in archive:
                        if member.name.replace("\\\\", "/").endswith("/bin/" + _DLL_NAME):
                            source = archive.extractfile(member)
                            if source is None:
                                break
                            data = source.read()
                            if not data.startswith(b"MZ"):
                                raise RuntimeError("Downloaded FriBiDi file is not a valid Windows DLL.")
                            temporary = _DLL_PATH.with_suffix(".dll.tmp")
                            temporary.write_bytes(data)
                            temporary.replace(_DLL_PATH)
                            break
            except Exception:
                _DLL_PATH.unlink(missing_ok=True)
                raise
            if not _DLL_PATH.is_file():
                raise RuntimeError("FriBiDi DLL was not found inside the verified MSYS2 package.")

        if _DLL_DIRECTORY_HANDLE is None:
            _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(_DLL_DIR))
        return _DLL_PATH

    return None

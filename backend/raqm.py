from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
import zstandard

from .storage import get_data_dir

_PACKAGE_PATH = (
    "/mingw/ucrt64/"
    "mingw-w64-ucrt-x86_64-fribidi-1.0.18-1-any.pkg.tar.zst"
)
_PACKAGE_URLS = (
    "https://repo.msys2.org" + _PACKAGE_PATH,
    "https://mirror.umd.edu/msys2" + _PACKAGE_PATH,
    "https://mirror.accum.se/mirror/msys2.org" + _PACKAGE_PATH,
    "https://ftp2.osuosl.org/pub/msys2" + _PACKAGE_PATH,
)
_PACKAGE_SHA256 = "4837d3626349c617aaa2db3d116f9b7ea208b11644f507a6a83eab36bb3ac920"
_DLL_NAME = "libfribidi-0.dll"
_DLL_DIR = get_data_dir() / "runtime" / "raqm"
_DLL_PATH = _DLL_DIR / _DLL_NAME
_INSTALL_MARKER = _DLL_DIR / ".fribidi-package-installed"
_DLL_DIRECTORY_HANDLE: Any = None


def _download_package() -> bytes:
    errors = []
    for url in _PACKAGE_URLS:
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            package = response.content
            if hashlib.sha256(package).hexdigest() != _PACKAGE_SHA256:
                raise RuntimeError(f"FriBiDi package checksum mismatch from {url}.")
            return package
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError(
        "Could not download the verified FriBiDi package from official MSYS2 mirrors:\\n"
        + "\\n".join(errors)
    )


def _install_fribidi_package() -> None:
    _DLL_DIR.mkdir(parents=True, exist_ok=True)
    package = _download_package()
    extracted: set[str] = set()
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
                filename = Path(normalized).name
                data = source.read()
                if filename.lower() == _DLL_NAME.lower() and not data.startswith(b"MZ"):
                    raise RuntimeError("FriBiDi package contains an invalid Windows DLL.")
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

    # Pillow's Windows wheel probes these historical DLL names. Keep aliases
    # beside the original MSYS2 filename so all supported Pillow versions find it.
    for alias in ("fribidi.dll", "fribidi-0.dll"):
        shutil.copy2(_DLL_PATH, _DLL_DIR / alias)

    _INSTALL_MARKER.write_text("verified MSYS2 FriBiDi package\\n", encoding="utf-8")


def ensure_raqm() -> Path | None:
    """Install FriBiDi and expose its DLL names before importing Pillow."""
    global _DLL_DIRECTORY_HANDLE

    if os.name == "nt":
        if not _INSTALL_MARKER.is_file() or not _DLL_PATH.is_file():
            _install_fribidi_package()
        else:
            for alias in ("fribidi.dll", "fribidi-0.dll"):
                alias_path = _DLL_DIR / alias
                if not alias_path.is_file():
                    shutil.copy2(_DLL_PATH, alias_path)

        if _DLL_DIRECTORY_HANDLE is None:
            _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(_DLL_DIR))
        return _DLL_PATH

    return None

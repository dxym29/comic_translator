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

# Official MSYS2 package. Use the primary server first: mirror.msys2.org
# geo-redirected this user's request to a mirror returning HTTP 403.
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
            digest = hashlib.sha256(package).hexdigest()
            if digest != _PACKAGE_SHA256:
                raise RuntimeError(
                    f"FriBiDi package checksum mismatch from {url}; refusing this download."
                )
            return package
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    details = "\\n".join(errors)
    raise RuntimeError(
        "Could not download the verified FriBiDi package from any official MSYS2 mirror:\\n"
        + details
    )


def _install_fribidi_package() -> None:
    _DLL_DIR.mkdir(parents=True, exist_ok=True)
    package = _download_package()

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
        if not _INSTALL_MARKER.is_file() or not _DLL_PATH.is_file():
            _install_fribidi_package()

        if _DLL_DIRECTORY_HANDLE is None:
            _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(_DLL_DIR))
        return _DLL_PATH

    return None

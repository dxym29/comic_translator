from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys


def remove_unused_legacy_package() -> None:
    try:
        version = importlib.metadata.version("simple-lama-inpainting")
    except importlib.metadata.PackageNotFoundError:
        return
    print(
        f"Removing unused legacy simple-lama-inpainting {version}; "
        "the current project uses its own TorchScript inpainting pipeline."
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "simple-lama-inpainting"],
        check=True,
    )


def reinstall_official_pillow_wheel() -> None:
    print("Reinstalling the official PyPI Pillow wheel without pip cache...")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--force-reinstall", "--no-cache-dir", "--no-deps",
            "--only-binary=:all:", "Pillow==12.3.0",
        ],
        check=True,
    )


def main() -> None:
    remove_unused_legacy_package()
    reinstall_official_pillow_wheel()

    from .raqm import ensure_raqm

    dll = ensure_raqm()
    if dll:
        dll_dir = str(dll.parent)
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

    from PIL import __version__ as pillow_version
    from PIL import features

    print(f"Pillow: {pillow_version}")
    if dll:
        print(f"FriBiDi DLL: {dll}")
        print(f"FriBiDi DLL exists: {dll.is_file()}")
    print(f"RAQM: {features.check('raqm')}")

    if not features.check("raqm"):
        try:
            from PIL import _imagingft
            build_flag = getattr(_imagingft, "HAVE_RAQM", "not exposed")
        except Exception as exc:
            build_flag = f"could not inspect _imagingft: {exc}"
        raise SystemExit(
            "RAQM is unavailable even after reinstalling the official Pillow wheel. "
            f"_imagingft.HAVE_RAQM={build_flag}. "
            "The current Pillow wheel was built without RAQM support; a custom "
            "Windows Pillow build is required. No downgrade was performed."
        )

    print("Pillow RAQM is ready.")
    print("Comic Translator local image environment is ready.")


if __name__ == "__main__":
    main()

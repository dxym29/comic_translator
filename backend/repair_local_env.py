from __future__ import annotations

import importlib.metadata
import subprocess
import sys


def remove_unused_legacy_package() -> None:
    try:
        version = importlib.metadata.version("simple-lama-inpainting")
    except importlib.metadata.PackageNotFoundError:
        return
    print(
        f"Removing unused legacy simple-lama-inpainting {version}; "
        "Comic Translator uses its own TorchScript inpainting pipeline."
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "simple-lama-inpainting"],
        check=True,
    )


def main() -> None:
    remove_unused_legacy_package()

    from .raqm import ensure_raqm

    dll = ensure_raqm()
    from PIL import __version__ as pillow_version
    from PIL import features

    print(f"Pillow: {pillow_version}")
    if dll:
        print(f"FriBiDi DLL: {dll}")
        print(f"FriBiDi aliases: fribidi.dll, fribidi-0.dll")
    print(f"RAQM: {features.check('raqm')}")

    if not features.check("raqm"):
        raise SystemExit(
            "RAQM is still unavailable. The verified FriBiDi DLL is installed, "
            "but this Pillow build did not load it. Do not downgrade Pillow; "
            "send this complete output for the next targeted fix."
        )

    print("Comic Translator local image environment is ready.")


if __name__ == "__main__":
    main()

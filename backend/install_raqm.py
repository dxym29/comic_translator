from __future__ import annotations

import platform
import sys

from .raqm import ensure_raqm


def main() -> None:
    dll = ensure_raqm()
    print(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    print(f"Python executable: {sys.executable}")
    if dll:
        print(f"FriBiDi DLL: {dll}")
        print(f"FriBiDi DLL exists: {dll.is_file()}")

    from PIL import __version__ as pillow_version
    from PIL import features

    print(f"Pillow: {pillow_version}")
    print(f"Pillow RAQM feature: {features.check('raqm')}")
    if not features.check("raqm"):
        raise SystemExit(
            "Pillow RAQM is unavailable. The FriBiDi DLL was installed, "
            "but this Pillow build could not load its RAQM runtime."
        )
    print("Pillow RAQM is ready.")


if __name__ == "__main__":
    main()

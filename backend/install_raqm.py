from __future__ import annotations

from .raqm import ensure_raqm


def main() -> None:
    dll = ensure_raqm()
    from PIL import features

    if not features.check("raqm"):
        raise SystemExit(
            "Pillow RAQM is unavailable. Check the Python architecture and FriBiDi DLL installation."
        )
    print("Pillow RAQM is ready.")
    if dll:
        print(f"FriBiDi DLL: {dll}")


if __name__ == "__main__":
    main()

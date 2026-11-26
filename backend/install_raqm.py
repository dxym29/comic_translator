"""Backward-compatible command; Myanmar rendering now uses Qt/HarfBuzz, not Pillow RAQM."""

from .repair_local_env import main


if __name__ == "__main__":
    main()

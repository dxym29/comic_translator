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
        "the current project uses its own TorchScript inpainting pipeline."
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "simple-lama-inpainting"],
        check=True,
    )


def install_qt_text_engine() -> None:
    print("Installing Qt's CPU text renderer (HarfBuzz shaping; no Pillow RAQM required)...")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--no-cache-dir",
            "--upgrade", "PySide6-Essentials>=6.11.3,<7",
        ],
        check=True,
    )


def main() -> None:
    remove_unused_legacy_package()
    install_qt_text_engine()

    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    print(f"PySide6: {pyside_version}")
    print(f"Qt runtime: {qVersion()}")
    print("Qt HarfBuzz text engine: ready")
    print("Comic Translator Myanmar typesetting environment is ready.")


if __name__ == "__main__":
    main()

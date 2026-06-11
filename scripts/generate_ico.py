#!/usr/bin/env python3
"""Regenerate the bundled Windows icon (``src/all2md/assets/icon.ico``) from the logo SVG.

The ``.ico`` is shipped in the wheel and referenced by the "View with all2md"
context-menu entry (see ``all2md context-menu``). Regenerate it whenever the
logo changes.

Requires ``cairosvg`` and ``Pillow`` (not part of the runtime deps):
    uv run --with cairosvg --with pillow python scripts/generate_ico.py
"""

from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = PROJECT_ROOT / "docs" / "source" / "_static" / "logo.svg"
ICO_PATH = PROJECT_ROOT / "src" / "all2md" / "assets" / "icon.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)]


def main() -> None:
    """Rasterize the logo SVG and write the multi-size ``.ico``."""
    png_data = cairosvg.svg2png(url=str(SVG_PATH), output_width=256, output_height=256)
    img = Image.open(io.BytesIO(png_data))
    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(ICO_PATH, format="ICO", sizes=SIZES)
    print(f"Wrote {ICO_PATH.relative_to(PROJECT_ROOT)} ({', '.join(f'{w}x{h}' for w, h in SIZES)})")


if __name__ == "__main__":
    main()

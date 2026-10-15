"""Record the README's animated GIF of ``all2md read`` -- without a terminal.

The viewer is driven headlessly through Wijjit's test harness, the styled screen
is captured after each scripted key, and the frames are rasterized with the
``_termshot`` helper from Wijjit's repository (it is not part of the installed
package). The same script always produces the same GIF.

The document shown is built here: Markdown converted to DOCX by all2md, then
read back, so the clip is of a Word file and depends on nothing outside the repo.

Usage
-----
From the repo root, with the ``tui`` and ``docx`` extras installed and Wijjit's
repository checked out beside this one::

    .venv/Scripts/python.exe scripts/make_readme_gif.py
    .venv/Scripts/python.exe scripts/make_readme_gif.py --wijjit ../wijjit --font PATH.ttf

Writes ``docs/source/_static/read-demo.gif``. The README embeds it by its raw
GitHub URL on ``main``, so PyPI shows it too.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "source" / "_static" / "read-demo.gif"
SIZE = (110, 32)

NL = chr(10)

# Single-width characters only: _termshot draws one glyph per cell.
DEMO = NL.join(
    [
        "# Field Station Annual Report",
        "",
        "The station logged its **busiest season** on record, with three new sensor",
        "arrays and a rebuilt data pipeline. This report covers the numbers, the",
        "methods, and what comes next.",
        "",
        "## Highlights",
        "",
        "- Uptime rose to *99.4%* across all arrays",
        "- Two new collaborators joined the [open data program](https://example.org/data)",
        "- The north mast was replaced ahead of the winter storms",
        "",
        "## Measurements",
        "",
        "| Array | Readings | Uptime | Mean temp |",
        "|:------|---------:|-------:|----------:|",
        "| North | 1,204,551 | 99.1% | -3.2 C |",
        "| Ridge | 987,310 | 99.6% | -5.8 C |",
        "| Lake | 1,451,002 | 99.5% | 1.4 C |",
        "",
        "Readings are corrected for sensor drift before they are averaged.",
        "",
        "## Methods",
        "",
        "Each reading passes through the same small pipeline:",
        "",
        "```python",
        "def corrected(reading, drift):",
        '    """Remove the measured drift from one reading."""',
        "    return reading.value - drift.at(reading.time)",
        "```",
        "",
        "> Data from the ridge array between March and May is provisional",
        "> while its calibration is reviewed.",
        "",
        "## Next season",
        "",
        "1. Extend the lake array to the eastern shore",
        "2. Move the archive to open formats",
        "3. Train two new volunteers on the maintenance rota",
        "",
        "See [Measurements](#measurements) for the baseline these goals build on.",
        "",
    ]
)

# (key, hold in ms); "" holds the current screen. Keys as in all2md.tui.keys.
# A panel's key toggles it; another panel's key switches to that panel.
STEPS: list[tuple[str, int]] = [
    ("", 2400),  # the document, outline beside it
    ("l", 2200),  # the links on screen, with their targets
    ("o", 800),  # back to the outline
    ("]", 1000),  # Highlights
    ("]", 1800),  # Measurements: the table
    ("]", 1800),  # Methods: code and the quote
    ("o", 1800),  # hide the outline
    ("?", 2400),  # the keys
    ("o", 600),  # the outline again
    ("home", 1600),
]


def main() -> int:
    """Build the demo document, drive the viewer and write the GIF."""
    parser = argparse.ArgumentParser(description=__doc__.split(NL)[0])
    parser.add_argument("--wijjit", default=str(ROOT.parent / "wijjit"), help="Wijjit's repository checkout")
    parser.add_argument("--font", help="monospace TTF covering box-drawing glyphs")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(args.wijjit) / "scripts"))
    from _termshot import find_font, parse_screen, render_frame  # type: ignore[import-not-found]
    from PIL import Image
    from wijjit.testing import WijjitHarness

    from all2md import convert, to_ast
    from all2md.options.terminal import TerminalRendererOptions
    from all2md.tui.app import Viewer
    from all2md.tui.layout import DocumentLayout

    fonts = find_font(args.font)
    cols, rows = SIZE
    frames: list[Image.Image] = []
    durations: list[int] = []

    with tempfile.TemporaryDirectory() as scratch:
        docx = Path(scratch) / "field-report.docx"
        convert(DEMO.encode(), str(docx), source_format="markdown", target_format="docx")
        layout = DocumentLayout(to_ast(str(docx)), TerminalRendererOptions())
        viewer = Viewer(layout, docx.name)
        with WijjitHarness(viewer.app, size=SIZE) as harness:
            harness.settle()
            for key, hold in STEPS:
                if key:
                    harness.press(key)
                    harness.settle()
                frames.append(render_frame(parse_screen(harness.screen_ansi()), fonts, cols, rows))
                durations.append(hold)

    # One palette for every frame, so colors do not shimmer between them.
    quantized = [f.quantize(colors=255, method=Image.Quantize.MEDIANCUT) for f in frames]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        OUT, save_all=True, append_images=quantized[1:], duration=durations, loop=0, optimize=True, disposal=2
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({len(frames)} frames, {OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

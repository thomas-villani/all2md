- **Born-digital lane re-recorded, and the fidelity page with it.**
  `benchmarks/pmc/reference.json` now holds the CI reading taken at `a83600a`. Against the
  reading v1.13.0 shipped with, on the same corpus pin and the same runner, so every
  movement is the parser's: recall of what is attainable 94.7% → **98.9%**, tables 69.1% →
  **82.7%**, titles 92.5% → **98.9%**, text blocks 97.2% → **99.4%**, supported share
  92.9% → **95.5%**, and novel share 1.00% → **0.43%** — less than half the text invented
  per emitted n-gram. Table recall moved on detection committing to borderless
  *booktabs*-style grids and on the row-fold repair in #449; the recall and precision gains
  are #405, #435, #441, #451 and the two column repairs in #445/#450 and #440. Every
  published figure on `docs/source/benchmarks.rst` is updated against the new artifact,
  including two the inventory does not gate.

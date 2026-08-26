- **Born-digital lane re-recorded, and the fidelity page with it.**
  `benchmarks/pmc/reference.json` now holds the CI reading taken at `1a80814`, replacing
  the one taken at `1226777` (#435). Same corpus pin, same runner, same PyMuPDF, complete
  corpus, so every movement is ours: recall of attainable 98.6% → **98.8%** (text blocks
  98.9% → **99.3%**), supported share 95.1% → **95.4%**, and novel share 0.81% → **0.43%**
  on the entity fix in #441 — emitted n-grams fell by 431 while *supported* ones rose by
  1,298, which is the arithmetic of text corrected rather than text dropped. Table recall
  is unchanged at 82.7%: the intermediate reading dipped to 80.9% on the row-fold defect
  in #448, and #449 returned it to the recorded figure exactly. Every published figure on
  `docs/source/benchmarks.rst` is updated against the new artifact.

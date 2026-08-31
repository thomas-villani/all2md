- **benchmarks/comparison: the heading measure's reading is published, and the lane's scope
  sentence stops excluding it.** The README claimed heading fidelity "requires all2md's page
  attribution and cannot score other tools", which stopped being true when
  `benchmarks/comparison/headings.py` landed — it matches a truth heading only against a
  heading the tool emitted, which needs no page attribution and so scores third-party output
  as readily as our own. Reading order and table *structure* are still all2md-only, and the
  sentence now says only that.

  Its first reading was recorded in a commit message and nowhere a reader would look, so it
  now sits with the lane's other readings: on the sealed holdout's 1,795 section headings,
  **all2md 76.4%, Docling 77.4%, pymupdf4llm 76.6%** of the headings the page actually
  printed. **Every tool loses about a quarter of them into the prose stream** and the three
  sit within a point of each other — a blind spot of the field rather than a place all2md
  trails. Two controls are quoted with it, because the shared vocabulary of
  `Introduction`/`Discussion`/`Funding` holds the whole-corpus control at 13.7%; on headings
  appearing in fewer than five articles it falls to 1.5%.

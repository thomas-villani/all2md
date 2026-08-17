- **The PMC born-digital lane runs again.** Moving the corpus fetchers' XML parsing to
  `defusedxml` left the scheduled `PMC Born-Digital Fidelity` workflow crashing at import:
  it syncs a deliberately lean environment (`--extra pdf_layout --extra ocr`), and
  `defusedxml` lived only in format extras the lane does not install, so the 2026-08-15
  scheduled run died in 29 seconds before scoring a page. A run that cannot execute also
  cannot count toward the lane's exit criterion (two consecutive clean scheduled runs
  before a fidelity baseline is recorded), so this was holding the gate open. What the
  benchmark lanes import beyond the library now has its own named home — a `benchmarks`
  extra — instead of borrowing from a format extra that happened to carry it.

- **The round-trip fidelity gate now also runs through man pages.**
  `python -m benchmarks.roundtrip --via man` sends each corpus document through a man
  page and back (`md -> AST -> man -> AST -> md`), and CI runs it beside the direct pass.
  Every document is a fixed point through man. A per-format profile in
  `benchmarks/roundtrip/via.py` projects man's inherent losses out of the HTML
  comparison: code languages, strikethrough, h4-h6, images, math markup and the like.
  The remaining failures are ratcheted in `MAN_EXPECTED_FAILURES`. Two are inherent
  (footnotes, raw HTML). Four are man-parser defects, each now visible: nested
  emphasis splits into runs, nested lists turn loose, task markers stay text, and
  links in table cells break.

- **PDF tables: a section heading is no longer folded onto the row above it** (#448). The
  first cut of #438 also folded any half-empty line group into a neighbour it abutted. A
  heading row *inside* a table — "Gender", with the indented "Male"/"Female" rows beneath
  it — fills one column and leaves the rest empty, which is exactly the shape of a wrapped
  fragment, so it was swallowed: its label fused onto the previous row's data and every
  value below it came out under the wrong heading. Silently mislabelled data is worse than
  the shredding the fold was meant to repair, and geometry cannot separate the two cases —
  one affected table prints a single body gap value, 1.56pt, for headings and data rows
  alike. The fold is removed; the gap-jump selection it shipped alongside is kept. Measured
  against JATS ground truth, removing it restores table content exactly on the born-digital
  corpus (7 pages that regressed recover, none lose) and improves the held-out corpus the
  fold was tuned on, where it had cost 5 table pages against 3 gained.

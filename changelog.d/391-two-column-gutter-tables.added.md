- **The word-gutter table pass admits two-column grids.** A single gutter is what any
  two-column layout has, so the pass shipped refusing it outright -- and that refusal
  cost the 4 real two-column tables still missing on the PMC born-digital corpus
  (`Questions | Answers`, `Male patients | 226 (69.8%)`) to save junk the downstream
  guards were already catching ([#389](https://github.com/thomas-villani/all2md/issues/389)).
  Measured, the corpus's whole two-column population is 12 regions: the 4 real tables,
  7 numbered reference lists, and 1 chart whose axis ticks and legend grid perfectly.
  Six reference lists were already condemned by the bibliography guard; the seventh
  numbered its entries `2)`, a spelling the guard's integer pattern now counts. The
  chart is caught by a new drawing-density gate that runs only at the two-column tier:
  a chart's labels float over its plot's vector paths (541 in the measured region)
  while a borderless table has at most its own rules (0-4 in all four real ones).
  Wider grids carry two aligned boundaries, which chart labels do not produce, so no
  established path changes.

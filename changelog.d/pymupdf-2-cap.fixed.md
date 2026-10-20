- **PDF conversion keeps PyMuPDF below 2.0 until 2.0 is evaluated.** PyMuPDF 2.0
  (released 2026-10-19) bundles `pymupdf-layout`, which it imports on every
  `import pymupdf`. Installed beside 1.17.0, that turned the layout model on for every
  PDF under the default `layout_analysis_mode="auto"`, about fifteen times slower on a
  short document and with headings one level deeper, and installed a process-wide hook
  that reroutes `find_tables()` through the model. It also changes table and paragraph
  extraction on its own: about half the born-digital development corpus converts
  differently with layout off. The `pdf`, `pdf_layout` and `all` extras now require
  `pymupdf<2`; supporting 2.0, and what `auto` should mean once layout ships with every
  install, is follow-up work measured on the benchmark lanes.

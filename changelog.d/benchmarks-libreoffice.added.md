- **benchmarks/libreoffice: real DOCX files, scored against what Word shows.**
  LibreOffice's Writer regression corpus (1,526 `.docx`, many attached to bug reports)
  is read by all2md and compared, as word multisets, with Word's own reading of each
  file over COM: main story, notes and text-box stories. It is the noisy counterpart to
  the scripted `benchmarks/docx` lane, and its first reading opened the DOCX fix stream
  of #531-#538 (export words missed 3,908 → 657, 267 of them math glyphs that all2md
  writes as LaTeX). `python -m benchmarks.libreoffice sweep` reads the corpus from a LibreOffice
  checkout, `compare` scores a sweep and, with `--against`, lists every file two sweeps
  read differently, which is how a reader change is judged. A manual instrument: no CI
  step. The Word reading is committed, dated and digest-pinned, since taking it needs
  Word; `word` re-records it.

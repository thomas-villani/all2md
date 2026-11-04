- **The OmniDocBench gate is green again, and a locked dependency bump can no longer
  turn it red unannounced.** Pillow 13 (#634) changed the baseline's recorded runtime, so
  the 2026-11-01 run reported identity drift with every score unchanged to the last digit.
  The baseline now records that run, and a per-PR test compares its PyMuPDF,
  pymupdf-layout, pytesseract and Pillow versions with `uv.lock`, so a bump fails on its
  own pull request rather than at the next monthly run. Tesseract and its language data
  come from the runner image, so only the gate itself can see them move.

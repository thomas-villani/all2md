- **DOCX: display equations are no longer dropped, and radicals no longer lose their
  contents.** Two defects, both found by the new `benchmarks/docx` lane on its first run,
  and both silent.

  Word writes a standalone display equation as a bare `m:oMath` element sitting directly
  under `w:p` — it only uses the `m:oMathPara` wrapper when an equation shares its
  paragraph with other content. The block extraction path accepted only `m:oMathPara`,
  and the inline path searched inside runs, which never sees it: `python-docx` yields
  only `w:r` and `w:hyperlink` children, so an `m:oMath` is invisible to `Paragraph.runs`
  and `Paragraph.text` alike. The equation fell between the two paths and was **dropped
  entirely** — not degraded, not misplaced, simply gone, with the surrounding paragraphs
  converting perfectly. Paragraph content is now walked in document order, so a bare
  `m:oMath` alone in its paragraph becomes a `MathBlock` (Word displays it as one and
  gives it the centred `Equation` style) while one sharing a paragraph with text becomes
  a `MathInline` **in its original position**, between the words it sits between rather
  than appended after them.

  The second was worse for being invisible. `_omml_handle_radical` looked for a child
  element named `m:base`, which is not in the OMML schema — the radicand is `m:e`, like
  every other OMML container. So every radical resolved to the empty string and vanished,
  taking its contents with it while the surrounding expression carried on looking
  entirely plausible: the quadratic formula converted to `\frac{-b±}{2a}`, which is
  well-formed LaTeX, renders without error, and is wrong. It is now
  `\frac{-b±\sqrt{b^{2}-4ac}}{2a}`.

  There were no OMML tests at all, which is how a handler naming a non-existent element
  survived; `tests/unit/test_docx_omml.py` now covers the conversion directly. The
  corpus check was tightened at the same time — it asked only whether anything
  math-like survived, which a radical that had silently emptied itself would have
  passed.

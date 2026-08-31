- **benchmarks/pmc: the ground-truth oracle can now be audited by running something, rather
  than by noticing.** `python -m benchmarks.pmc.audit` carries five checks over a cached
  corpus — where blocks sit against the attainable bar, what the `MIN_NGRAMS` floor removes,
  what the published `title` row is actually made of, blocks repeating another block's text,
  and projected words the PDF's text layer never holds. None of them convert anything, so
  each runs in about a minute. They exist because the projection's element-boundary space
  (#470) went unexamined for months while every figure in the lane rested on it, and the
  penalty it produced was several times larger than the structural defect it hid.

  The first run found three things clear and one not. The 0.80 attainable bar is sharply
  bimodal on both development corpora and so is not a knife edge; duplicate truth blocks are
  0.19% and benign under set containment; and the 2.6% of projected words the text layer
  lacks (ORCID digits, institution identifiers, licence URLs) sit in blocks the ceiling
  already excludes. But the floor never scores **22.6% of ground-truth blocks, including 41%
  of titles** — and of the title blocks that are scored, 2,208 are reference-list entries
  against 148 section headings, because `Introduction` and `Discussion` are two words. The
  published `title` figure is largely a statement about reference lists. Tables are
  unaffected at 0% unscored.

- **benchmarks/comparison: section headings can be scored, and across every tool.** A truth
  heading counts as recovered only when the converter emitted a *heading* with the same text
  — structure rather than containment, which is what makes it immune to the floor problem
  above and to `Introduction` appearing in every article's prose. It needs no page
  attribution, so unlike reading order and table structure it scores third-party output as
  readily as our own. On the sealed holdout's 1,795 section headings, **every tool loses
  about a quarter of them into the prose stream**: all2md recovers 76.4% of printed
  headings, Docling 77.4%, pymupdf4llm 76.6%. Two controls are reported, because scoring an
  article against the wrong output still matches 13.7% on a shared vocabulary of
  `Introduction`/`Discussion`/`Funding`; restricted to headings appearing in fewer than five
  articles the control is 1.5% and all2md reads 77.1%.

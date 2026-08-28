- **benchmarks/pmc: the held-out corpus was redrawn, and the rule that keeps it held out
  is now a test.** The 110-article corpus drawn at `--seed-offset 250000` had stopped being
  held out: an audit found its article ids in six tracked files, five of them source or
  tests, each one a threshold or strategy chosen against held-out data — the column-crossing
  tolerance, the footer height-share band, the gridded-prose dominance bar, a table
  transcribed verbatim as a fixture, and a comment in `_pdf_tables.py` citing one of its
  articles as "the worst table on the corpus". That is wider than the column axis previously
  believed to be affected; the table figures were in-sample too. It is retained as a second
  development corpus (`manifest-tuned.json`) rather than deleted, because those exemplars
  are real and the tests citing them are good tests. A fresh **103-article** holdout is
  drawn at `--seed-offset 125000`, verified disjoint from both development corpora, and
  materializes under its own cache root so reaching for it takes a deliberate act rather
  than a default path. `tests/unit/test_pmc_holdout_seal.py` fails if any tracked file names
  a held-out article — run against the retired corpus, it catches all six historical leaks.
  The fresh corpus is deliberately **not scored yet**: every comparison figure published
  before 2026-08-27 is an in-sample reading and is now labeled as one.

- **benchmarks/pmc: the born-digital filter's second arm is not only a backstop, and the
  corpora under-represent short graphics-free articles.** Twenty of the new draw's 22
  era-seeds returned a full five articles; two returned none and three, both exhausting
  their candidate budget on `no_vector_drawings` — an arm that had fired exactly zero times
  across both earlier builds. The regions were probed rather than assumed. One deposits
  rasterized pages that still carry a text layer and JATS paragraphs, where the arm is doing
  its documented job; the other deposits short born-digital pieces with a real text layer
  and no graphics at all, which the filter rejects even though they are born-digital by
  every meaning the corpus intends. The filter is left unchanged, because changing it
  between corpora would cost the comparability that makes the three sets worth having, and
  the quota was not forced by walking further into a barren run — that would draw five
  articles from the one publisher's template that made it barren. 103 articles across 20
  eras is the honest draw.

- **benchmarks/comparison: first reading of the sealed holdout, and the table gap is three
  times wider than the tuned corpus showed.** 103 of 103 articles converted by all three
  tools with zero conversion or parse failures. all2md keeps the invented-text lead that
  the lane exists to measure — **0.55% novel share** against Docling's 2.05% and
  pymupdf4llm's 6.26%, barely moved from the in-sample 0.62%, which is what an honest
  number does when the corpus changes underneath it — and leads raw precision at 93.9%.
  Recall is a three-way tie inside 0.65 points. The cost of the seal: **table-text survival
  reads 69.7% against Docling's 86.4%, a 16.7-point gap where the burned corpus showed
  4.8.** Both tools moved, so this is not a regression; it is the old gap having been
  measured against data the table work was developed on. Two claims are retired with it:
  all2md is no longer the worst table over-emitter (226/164, against pymupdf4llm's 276 and
  Docling's 206), and the reading's speed column is not comparable across readings — every
  tool measured 1.8-2.5x slower than its own record in the session, while a v1.13.0
  worktree measured within 2% of HEAD, so it is ambient machine state and should be read as
  an ordering only.

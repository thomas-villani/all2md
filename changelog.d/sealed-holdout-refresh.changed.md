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

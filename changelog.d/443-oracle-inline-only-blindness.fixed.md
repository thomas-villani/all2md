- **Benchmark oracle: a container of inline text counts as text again** (#443). The shared
  AST projection recognised block types by name and recursed through everything else, so a
  node holding inline content *directly* — with no `Paragraph` wrapper — fell through the
  walk and contributed nothing. `DefinitionTerm` is the shape that exposed it: the term
  vanished while its sibling `DefinitionDescription` survived, and survived only because it
  happens to wrap its own content in a `Paragraph`. The projection now admits any container
  of inline text by that *shape* rather than by a list of type names, so the next node built
  the same way cannot reproduce the bug in silence — while comments, which carry text but
  never print, stay excluded. On the held-out 110-article corpus this recovers 130 words
  across 3 all2md files and 1 word of docling's, and **5 of the 113 blocks the 2026-08-23
  lost-block census attributed to conversion defects turn out to have been emitted
  correctly all along** — 3 of them titles. Both PDF lanes are unaffected: the PDF parser
  emits no definition lists and wraps every list item in a `Paragraph`.

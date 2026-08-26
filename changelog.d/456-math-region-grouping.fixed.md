- **PDF: an equation split across several blocks is now recognised as one equation**
  (#456). PyMuPDF splits a display equation wherever its glyphs stop lining up, so the
  operators land in one block, the variables in the next and a lone subscript in a third.
  Only some of those blocks carry font evidence; the rest are indistinguishable from prose
  by any test applied to them alone, so ``equation (19b)`` still arrived as
  ``*e* *c* *e* *S* *m* *R*`` after the per-block fix. Which blocks belong to an equation
  is now decided for the whole column: blocks that carry their own evidence seed the
  answer, and the seeds spread to a neighbouring *glyph run* — a block of more printed
  lines than words, which is what a column of stacked glyphs looks like — printed hard
  against one. Spreading is transitive, so an equation reaches its far side one block at a
  time, and it stops at the first block that reads as text. Both halves of the test are
  needed: on a page a third of which is equations, contiguity alone takes 764 blocks
  rather than 367 and whole sentences among them, while the glyph-run signature alone
  admits table data rows — ninety-nine of them in a dev-corpus article with no equations.
  Together, over twenty-six articles, they admit 367 blocks across the five that carry
  display equations and none at all across the twenty-one that do not; the distance test
  is what keeps a running head, shredded the same way, out of the first equation below it.
  This removes a further 1,562 emphasis markers — PMC3000079.1's count more than halves,
  2,828 to 1,490 — while three control articles are byte-identical and prose italics
  (``*Int. J. Mol. Sci.*``, ``*zitterbewegung*``) are untouched.

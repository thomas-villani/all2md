- **PDF: a display equation's variables are no longer emphasised one glyph at a time**
  (#456). An equation is typeset glyph by glyph — each variable, operator and bracket piece
  its own span in its own font — and an italic variable is italic *because it is a
  variable*. Wrapping each one separately produced ``*e* *c* *e* *S* *m* *R*``: markup
  asserting that a dozen single letters are each stressed, which is neither what the page
  means nor anything a reader or a model can use. A line is now recognised as part of a
  display equation when two things hold together — it carries math evidence (30%+ of its
  spans in a symbol or TeX math font, or a Private Use codepoint anywhere in it) and it is
  at most six words. Either test alone claims real prose: 36 corpus lines of 11–24 words
  carry a symbol span while being sentences merely *about* mathematics, and a page is full
  of short italic lines. Because the evidence is not spread evenly down an equation — one
  line carries the operators in a symbol font, the next only the variables in the ordinary
  text italic — a block whose lines are half equation lines carries the rest with it.
  Measured over 9,417 lines of three equation-heavy articles and two without: 99% of
  evidence-bearing lines hold two words or fewer, the first prose line to carry evidence
  holds ten, and every word cap between 3 and 8 admits the same lines and no prose at all.
  Across the three articles this removes 1,154 emphasis markers; both control articles are
  byte-identical, and prose that names its variables in italics — ``mass (*m*), velocity
  (*v*), charge (*e*)`` — keeps them.

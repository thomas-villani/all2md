- **benchmarks/docx: the generation side of a scripted DOCX ground-truth lane.** DOCX is
  the next fidelity frontier and its defects are already named — tracked changes vanish
  silently, `HYPERLINK`/`REF`/`SEQ` fields are never read, style-inherited numbering is
  lost on exactly the corporate templates that use it — but until now the only instrument
  pointed at them was the round-trip score, which is self-referential: a parser and a
  renderer that agree on a wrong reading score perfectly.

  There is no bucket of DOCX files with independent structural truth beside them, the way
  PMC pairs a publisher's PDF with its JATS. So the truth is generated: a case script
  drives a live Word over COM through [`wordlive`](https://pypi.org/project/wordlive/),
  and because the script knows exactly what it put in the document it can write an
  expected-facts record beside it — while Word's own serializer produces the file, so the
  markup is what Word really writes rather than what a Python writer believes Word writes.
  That keeps truth and artifact coming from different tools, which is what makes the PMC
  lane trustworthy. It also buys something a collected corpus never can: paired
  minimal-difference documents, two files identical but for one construct.

  This release lands the design and the Word-driving machinery, with every generation
  recipe already verified in saved XML — raw field codes, real `w:ins`/`w:del`,
  style-inherited numbering through a `LinkToListTemplate` hatch, content controls with a
  genuine `w:showingPlcHdr`, style-carried formatting. Generation cannot run in CI, so it
  is quarantined in `benchmarks/docx/generate/` and the corpus bytes will be committed and
  digest-pinned for CI to replay. No corpus, no oracle and no gate yet, deliberately — the
  same order `benchmarks/pmc` landed in.

  One measurement ships with it. `numfmt-map.json` records what OOXML `w:numFmt` value
  each Word `WdListNumberStyle` constant actually writes, measured rather than read off
  the documentation because the constant names mislead (the one named `GBNum1` writes
  `decimalEnclosedFullstop`; `chineseCounting` comes from a different constant entirely).
  It sizes a defect as a side effect: Word writes **46 distinct `w:numFmt` values and the
  DOCX parser recognises five**, so the other 41 leave an ordered list undetected as
  ordered — and that unrecognised set is almost entirely CJK, Hebrew and Arabic numbering.

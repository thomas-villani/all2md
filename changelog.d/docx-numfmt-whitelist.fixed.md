- **DOCX: ordered lists numbered in Chinese, Japanese, Korean, Hebrew or Arabic script are
  no longer silently turned into bullets.** The parser recognised five `w:numFmt` values —
  `decimal`, `lowerLetter`, `upperLetter`, `lowerRoman`, `upperRoman` — out of the 46 Word
  actually writes. Everything else fell through to a text sniff that defaults to bullet, so
  the list survived, the item text survived, and the *numbering* quietly did not. The set
  being dropped was not a random tail: it is almost entirely CJK, Hebrew and Arabic
  counting schemes, plus everyday Western ones like `decimalZero` and the enclosed and
  full-width digits.

  The test is now for the exceptions rather than for a list of knowns. ECMA-376
  ST_NumberFormat enumerates some sixty schemes and only `bullet` and `none` are not a
  counter of some kind, so everything else is ordered — including `custom`, whose glyph
  lives in `w:numFmtCustom`, and including any value a future Word invents. Guessing
  "ordered" is the safe direction for an unknown value: it is far more likely to be one of
  the fifty-odd counting schemes than one of the two that are not.

  Measured on a sweep of every scheme Word writes, applied to a real Word-generated list:
  5 of 50 rendered as an ordered list before, 48 of 50 after, with `bullet` and `none`
  correctly the two that do not.

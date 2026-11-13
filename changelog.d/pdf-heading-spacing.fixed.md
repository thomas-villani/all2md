- **PDF → Word keeps the space around headings.** Converted headings kept Word's own
  spacing (24pt above Heading 1, 15pt under the Title, with a rule beneath it) whatever
  the PDF used. Each `heading_styles` level now also records `space_before` and
  `space_after`, read from the body lines just above and below its headings the way
  Word lays lines out: a font's Windows ascent above the baseline, its descent below,
  and the larger of two paragraphs' facing spaces between them. The DOCX renderer sets
  them on the heading styles, set single-spaced, and drops the Title's rule. On the
  Word-made test documents every heading now lands within a fifth of a point of where
  the PDF printed it.

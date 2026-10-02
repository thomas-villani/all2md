- **pdf: TeX math symbols embedded without a Unicode map are read.** TeX's math symbol
  (cmsy) and extension (cmex) fonts put glyphs at codes 0x00-0x1F, and a PDF that
  embeds them without a ToUnicode map gave those codes as they are: "Scoring ≥50%"
  arrived as "Scoring" followed by a control character, which the DOCX and EPUB
  renderers then dropped. Codes 0x00-0x1F in those fonts are now mapped through the
  published tables (≥, ≤, −, ∗, •, ±, ×, … and cmex's delimiters), in body text and,
  on a page with one such font, in table cells. Fonts re-encoded per document are left
  as they are.

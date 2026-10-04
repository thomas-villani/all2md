- **docx: two tables in a row stay two tables in Word.** The renderer wrote adjacent
  tables with nothing between them, and Word shows two tables that touch as one, so
  a 13 × 14 table followed by a 13 × 13 one opened as a single 26 × 14 table. The
  DOCX parser read them back as two, so only Word saw the join. The renderer now keeps
  an empty paragraph between them, as Word itself does. A caption or any other block
  between two tables already separates them and adds nothing. Found by the PDF → DOCX
  Word read-back (`benchmarks.pmc word`): 5 pairs in 5 of 66 development-corpus
  articles.

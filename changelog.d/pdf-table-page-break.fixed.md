- **A PDF table split by a page break is one table again.** Word carries a long table
  over to the next page at the same x positions, often repeating its header row there,
  and the converter read it as two tables with the page's footer and the next page's
  running header between them. When one page ends in a table and the next begins with
  one that has the same columns at the same left and right edges, with only margin text
  between them, the second table's rows now join the first; a repeated header row is
  dropped, and the footer and header text move after the joined table. Across 990
  public PDFs (GovDocs1, Common Crawl, EDGAR contracts) 129 continuations join, in 30
  documents; no word leaves any document, and the only words dropped are repeated
  header rows. `join_split_tables=False` (`--pdf-no-join-split-tables`) turns this off.
- A table's last row is no longer printed a second time after the table when Word's
  empty paragraph below the table falls in the same text block. Such a block now
  belongs to the table when its printed lines lie inside it, as well as when most of
  its area does; the first test applies only to blank lines just below the text, so
  text crossing a table's edge (a rotated heading beside a landscape table) stays put.
  It removes a doubled total or last row in 8 of the 990 documents.

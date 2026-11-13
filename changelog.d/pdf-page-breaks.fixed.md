- **PDF → Word keeps the page breaks the author put in.** A section the PDF started on a
  new page ran on below the previous one in Word, so the document came out shorter and
  every later page broke somewhere else. A page counts as ended on purpose when it
  stopped with room to spare for what opens the next page (its first three lines of
  text, as Word keeps a heading with the two lines after it, or a figure or table that
  opens it, whole), or when the next page is a different size. The block that opens the
  new page gets `page_break_before` in its metadata, and the DOCX renderer sets Word's
  "Page break before" on it. Markdown output is unchanged.
  `keep_page_breaks=False` (`--pdf-no-keep-page-breaks`) turns it off.

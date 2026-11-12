- **A PDF's running header and footer leave the body.** Word prints a document's header
  and footer on every page, and the converter read them as body paragraphs: the header
  above page 1's title, a footer and the next header between every two pages of text.
  A line repeated at the same place in the outer tenth of the page on two or more pages,
  clear of where the body starts, with nothing between it and the page edge and outside
  any table, is now taken out of the body and kept in the document metadata as
  `page_header` / `page_footer`. Other distinct running lines (an even page's running
  head beside an odd page's) are kept in `page_header_alternates` /
  `page_footer_alternates`. A page number that steps with the page becomes `{page}` and
  the page count `{pages}`, so `Lease, page 3` is kept as `Lease, page {page}`; when
  the numbering starts somewhere other than 1, `page_number_start` records where. A
  single-page PDF is never searched. `extract_running_headers_footers=False`
  (`--pdf-no-extract-running-headers-footers`) restores the old output;
  `trim_headers_footers` and `auto_trim_headers_footers` still delete margin text instead.
- **PDF → Word writes a real header and footer.** The DOCX renderer turns `page_header`
  and `page_footer` metadata into the document's Word header and footer, `{page}` and
  `{pages}` as live `PAGE` and `NUMPAGES` fields, and starts the page numbering at
  `page_number_start`.

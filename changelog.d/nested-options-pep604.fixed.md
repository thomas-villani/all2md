- **HTML options passed as keyword arguments reach the HTML inside EPUB and CHM files.**
  `to_markdown("book.epub", base_url=...)`, or any of the 18 HTML options the EPUB and
  CHM options don't have themselves, was ignored with a warning on Python 3.11–3.13
  instead of going to their `html_options`. Those fields are annotated `HtmlOptions | None`,
  which two of the three paths that build nested options missed: they tested for
  `__origin__`, which `X | None` lacks before Python 3.14. The three paths now share one
  helper. The CLI was not affected.

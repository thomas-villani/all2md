- **PDF → Word keeps the paper size, orientation and margins.** A converted document
  came out on portrait US Letter with one-inch margins whatever it was printed on, so an
  A4 lease and a landscape financial summary changed shape. The PDF parser now records a
  `page_setup` metadata entry: the commonest page size (and `orientation: landscape`),
  and, on documents of two or more pages, the margins and the header and footer
  distances, read from where the body text starts and stops and snapped to the values
  documents are set with (eighth-inch steps, whole and half centimetres). The bottom and
  right margins mirror the top and left unless the text demonstrably runs further: a
  page's text stops short of them for many reasons, so a shorter page proves nothing.
  The DOCX renderer applies it to every section; a reference template keeps its own
  page setup.

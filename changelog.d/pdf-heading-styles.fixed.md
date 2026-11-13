- **PDF → Word keeps how the headings looked.** Converted headings came out in Word's
  built-in 14pt and 13pt styles whatever the PDF used, so a lease headed in 20pt
  Calibri Light ran a page short in Word. The PDF parser now records a
  `heading_styles` metadata entry: for each heading level, the size, font, weight and
  color most of its headings were printed in (a bold title set at the body size takes
  the body's size and font). The DOCX renderer applies them to the Heading styles, and
  to Title when a leading heading is promoted to it; sizes passed in
  `heading_font_sizes` win, and a reference template keeps its own.

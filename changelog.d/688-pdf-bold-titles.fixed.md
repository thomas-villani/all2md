- **PDF section headings set in bold at the body size are now headings.** Contracts, and
  EDGAR filings in particular, set their section headings in bold at the size of the text
  (`ARTICLE 5 INDEMNIFICATION`, `9.1 Notices`), so the font-size rules could not admit
  them: 120 contracts from CUAD produced 11 headings between them, and a bold title often
  ran into the paragraph below it. A paragraph is now cut where the weight changes, and
  a short paragraph set all in bold (at most two lines and twelve words) becomes a
  heading ranked under any heading admitted by size. It does not when it reads as prose,
  or when it is a caption or figure label (`Table 1`, `E E E E`), a contents-page entry
  or column (`Page`, a dot leader), a running head with its page number, or a bullet; with
  layout analysis on, lines the model places in a figure, list, table, caption or page
  header are left alone. `header_use_font_weight=False` turns it off. Run-in headings
  (`**5. Indemnification.** The Company shall ...`) are not split yet.
- On the PMC born-digital dev corpus with layout analysis off, section-heading recall rises
  from 23.4% to 38.4% and precision from 51.9% to 54.7%, with no heading lost; block
  structure rises 0.0162 with layout analysis off and moves -0.0005 with it on, and text,
  reading order and tables do not move.

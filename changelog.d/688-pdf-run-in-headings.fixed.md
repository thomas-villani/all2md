- **PDF run-in section titles are split from their text.** Contracts often set a clause's
  title in bold at the head of its first line and run the text on after it
  (`**5. Indemnification.** The Company shall ...`, `8.1 **Term**. This Agreement ...`),
  so no line was all bold and the clause stayed one paragraph with a bold opening. The
  title now becomes a heading, ranked with the bold titles set on their own line, and the
  text after it a paragraph. A title must end in `.` or `:` (or carry its own number,
  `**9.6 Expiration** Upon ...`), be followed by a sentence, and pass the bold-title
  checks; defined terms (`**"Affiliate"** means`), notes (`**Note:**`), attestations
  (`**IN WITNESS WHEREOF,**`), an article's front-matter fields (`**Received:**`,
  `**Citation:**`, contributor roles), caption labels, a reference entry's bold author,
  bold sentences and drop caps are left alone. A line that
  opens in bold after a sentence ends now starts a new paragraph, so one clause no longer
  runs into the next. Bold titles also lose a closing `.` or `:` (`3. COMPENSATION.`
  becomes `3. COMPENSATION`), and a blank line set in the regular weight above a bold
  title no longer keeps it from being one. `header_use_font_weight=False` turns this off.
- On 120 CUAD contracts the run-in rule adds 285 clause headings across 21 contracts; a
  hand sample of 50 found all 50 real. On the PMC born-digital dev corpus with layout
  analysis off, section-heading recall rises from 38.4% to 41.5% with no heading lost
  (precision 54.7% to 54.2%); block structure rises 0.0025 with layout analysis off and
  0.0027 with it on, and text, reading order and tables do not move.

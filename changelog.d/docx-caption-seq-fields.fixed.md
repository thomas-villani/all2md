- **docx: Word numbers figure and table captions.** Captions carried Word's Caption
  style but their numbers were plain text, so Insert Table of Figures and
  cross-references found nothing. A caption's number is now the `SEQ Figure` or
  `SEQ Table` field Word's Insert Caption writes, with the printed number as its cached
  result, so the text reads and parses back unchanged. Word renumbers these fields 1, 2,
  3 when fields update, so a field is written only where that changes nothing: a plain
  integer after "Figure", "Fig." or "Table" that continues the label's sequence. After a
  break (a figure printed only as a graphic, "Figure S1", "Figure 1A", "Table 1.2"), that
  label's later numbers stay text. On a 12-article PMC subset, 24 of 29 captions get a
  field, and updating every field in Word changes none of the 29.

- **docx: text inside `w:dir`, `w:bdo`, `w:smartTag` and `w:customXml` is read.** Each
  of these wraps ordinary runs to set their direction (Word writes `w:dir` and `w:bdo`
  around Arabic and Hebrew text), tag a recognized name or date, or bind them to a
  custom schema, and each put its runs one level below where the paragraph reader
  looked, so the text vanished from the middle of its sentence. A block-level
  `w:customXml` hid a whole paragraph, table, row or cell the same way. They are now
  unwrapped on the element tree before reading, as content controls already were; the
  wrapper's own properties are dropped, and right-to-left text is written in the reading
  order Word stores it in. On LibreOffice's Writer regression corpus one Arabic file had
  lost all 71 of its words, and the words missed overall fell from 781 to 653.

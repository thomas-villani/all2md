- **docx: heading levels survive a round trip when the leading H1 is not the title.**
  The renderer writes a leading H1 in Word's Title style and moves the headings after
  it up one level, and the parser undoes that shift when the title leads. Two shapes
  broke it:
  - **A second H1.** It was written as "Heading 1", the same as the old H2s, so H1 and
    H2 came back as one level.
  - **A picture ahead of the H1.** A journal logo counted as an empty spacer when
    writing, but is content when reading back, so the shift was not undone and every
    heading came back a level too high.

  Title promotion now applies only when the leading H1 is the document's only top-level
  H1 and nothing but blank paragraphs comes before it. Found by the second full reading
  of the PDF → DOCX re-parse ledger (PMC10000026.1, PMC8000039.1).

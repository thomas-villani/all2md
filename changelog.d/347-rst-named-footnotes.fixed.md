- **reST footnotes survive a round trip with their identifiers and paragraphs.**
  Three defects stacked ([#347](https://github.com/thomas-villani/all2md/issues/347)):
  the renderer spelled every footnote `[a1]_` / `.. [a1]`, which for an
  alphanumeric label is reST *citation* syntax, so the footnote stopped being
  one -- non-numeric identifiers now use the named auto-numbered form
  (`[#a1]_` / `.. [#a1]`), with escaped whitespace (`word\ [#a1]_`) where a
  marker rides a word, since docutils only starts inline markup after a
  boundary. A multi-paragraph definition rendered as continuation lines and
  read back as one paragraph -- its blocks now separate with blank lines at
  the marker's body column, and hard breaks inside a body fall back to raw
  newlines so `| ` line-block syntax cannot displace it. And the parser
  preferred docutils' normalized anchors (`ids`, e.g. `footnote-1`) over the
  label as written (`names`), mangling identifiers even for plain numbered
  footnotes; it now takes the name on both definitions and resolved
  references, and resolves docutils' internal `\x00` escape markers instead
  of copying them into text.

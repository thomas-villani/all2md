- **reST and Org definition descriptions no longer fuse or lose words.** Both
  renderers concatenated a description's paragraphs with nothing at all between them,
  so `alpha` and `beta` came back as the single token `alphabeta` -- a destroyed word
  boundary, not a lost break ([#352](https://github.com/thomas-villani/all2md/issues/352)).
  The reST renderer now separates blocks with a blank line at the same indent, which
  round-trips the paragraph count exactly; the Org renderer joins blocks as indented
  continuation lines, so the boundary degrades to a line rather than a fused word.
  Worse than the reported fusion, the Org *parser* silently deleted every definition
  line that did not start a new `- term ::` item -- a wrapped definition lost all but
  its first line; continuation lines now join the open definition. A term's several
  descriptions still flatten into the one definition each syntax can hold (docutils:
  one definition per term; Org: one `::` per item) -- words intact, count inherently
  lost -- and the fuzzing-gate entries now say exactly that.

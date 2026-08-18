- **DokuWiki footnote definitions no longer fuse their paragraphs into one token.**
  A multi-paragraph definition was rendered through the inline path with nothing
  between the blocks, so `first para` and `second para` came out `first parasecond
  para` -- a destroyed word boundary, the same corruption class fixed for reST and
  Org definition lists ([#347](https://github.com/thomas-villani/all2md/issues/347)).
  Blocks now render separately and join with a space. The paragraph boundary itself
  is still lost -- DokuWiki's inline footnotes have nowhere to carry it -- and the
  round-trip fuzzing gate continues to document that; the words survive.

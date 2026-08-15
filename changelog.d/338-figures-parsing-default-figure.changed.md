- **HTML `figures_parsing` now defaults to `"figure"`.** A `<figure>` element
  parses to the `Figure` AST container introduced alongside
  [#338](https://github.com/thomas-villani/all2md/issues/338) — children plus a
  `caption` — instead of degrading to a `BlockQuote` with the caption folded
  into its prose. Callers that read the caption as paragraph text should read
  `Figure.caption`; the previous behaviour remains one option away
  (`figures_parsing="blockquote"`). With the default flipped, the generative
  figure round-trip gate now covers HTML alongside `ast` and `markdown`.

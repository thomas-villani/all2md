- **The AST has a home for figures: a `Figure` block container with children
  and a caption.** A figure is not always one image — multi-panel journal
  figures embed one raster per panel, LaTeXML wraps every arXiv table in
  `<figure>`, and a vector-drawn PDF figure has a caption and no raster at all,
  which `Image.caption` alone could not represent
  ([#338](https://github.com/thomas-villani/all2md/issues/338)). `Figure` holds
  block children (possibly none) plus an optional `caption: str`, mirroring
  `Table.caption`. All 16 renderers emit it — natively where the format has a
  spelling (HTML `<figure>`/`<figcaption>`, reST's `figure` directive, LaTeX's
  `figure` float, AsciiDoc block titles, org `#+CAPTION:`), children plus an
  italic caption line elsewhere — and Markdown round-trips it through an
  extent-based variant of the #237 marker device (`<!-- all2md:figure -->` …
  `<!-- all2md:figure-caption -->`/`<!-- all2md:figure-end -->`). The HTML
  parser gains an opt-in `figures_parsing="figure"` mode that reads
  `<figure>` back as the container (made the default in a separate change,
  noted below); the PDF parser does not emit `Figure` yet — that follow-up is
  its own deliberate change. `NodeVisitor.visit_figure` is
  concrete rather than abstract (the `visit_mark` precedent), so third-party
  visitors degrade to the figure's children instead of crashing; the
  `figure:`/`image:` extraction selector now returns a multi-panel figure as
  one figure rather than N images.

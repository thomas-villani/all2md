- **The PDF parser emits `Figure` containers.** A captioned raster is now
  wrapped in a `Figure` with the caption on the container (it used to ride on
  `Image.caption`, both unreleased), panels grouped by a layout `picture`
  region or an identical detected caption fold into one multi-panel figure,
  and a `picture` region holding no raster at all — a vector-drawn chart —
  becomes a caption-only `Figure`, because the caption is the only record the
  figure exists ([#338](https://github.com/thomas-villani/all2md/issues/338),
  [#340](https://github.com/thomas-villani/all2md/issues/340)). The `picture`
  region also rescues captions the per-image search cannot reach: a stacked
  panel's below-band finds the next panel, not the caption, while the region's
  extent ends where the caption starts. Caption body-copy suppression now
  follows emission: when OCR replaces a page or `image_placement_markers` is
  off, no figures are emitted and caption paragraphs are no longer dropped
  from the text. Measured on the 12-article PMC born-digital sample,
  `figure_binding` rose 0.47 → 0.56 (19 of 34 captions bound, both controls
  held at zero); the newly bound captions leave the prose stream, the same
  trade every bound caption already makes. The PMC oracle now counts a
  `Figure` container once — not once per panel — matching JATS `<fig>`
  granularity.

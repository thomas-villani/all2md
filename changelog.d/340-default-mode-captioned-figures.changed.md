- **Default options no longer drop every PDF figure silently.** The default
  `attachment_mode="alt_text"` returned before extracting anything, so a journal
  PDF's figures left no trace — a 23-page arXiv paper with 251 embedded rasters
  produced zero `Image` nodes ([#340](https://github.com/thomas-villani/all2md/issues/340)).
  The mode now runs a decode-free geometry pass and emits the figures that carry
  a detected caption, as URL-less `Image` nodes whose caption renders through
  the caption marker device. Uncaptioned images stay suppressed under that mode:
  with no bytes and no caption, an `![alt]()` placeholder is noise, which was
  the sound half of the old rationale
  ([#338](https://github.com/thomas-villani/all2md/issues/338)). No pixmap is
  decoded on this path, so the default mode keeps its performance edge over
  `save`/`base64`. Vector-drawn figures still yield nothing — they emit no
  raster placement to hang a caption on, and reaching them is #338's
  caption-bearing container, deliberately not attempted here.

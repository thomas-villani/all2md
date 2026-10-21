- **The OCR extras need Pillow 13.0.0 or later.** Pillow 13.0.0 fixes nine advisories in
  its JPEG, TIFF, GIF, EPS and PDF readers, one of them critical (a heap buffer overflow in
  `ImagingJpegDecode`). all2md's own use of Pillow only builds images from pixels PyMuPDF
  has already rendered, so it never reached those readers. But Pillow is also what the
  libraries we call use to open pictures embedded in documents, and documents are often
  untrusted, so `ocr`, `ocr-easyocr` and `all` now require `pillow>=13.0.0`. OCR on an
  older Pillow stops with a `DependencyError` that names the version it needs.

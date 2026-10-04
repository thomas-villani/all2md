- **docx: rendered documents no longer open in Compatibility Mode.** python-docx's
  default template sets Word 2010's compatibility mode (14), so Word opened every
  document the renderer wrote with "[Compatibility Mode]" in the title bar and its
  newer layout rules off. The renderer now writes mode 15, the one Word gives a document
  it creates. This turns on Word 2013's layout rules, so line breaking and table layout
  can shift slightly. A template passed as `template_path` keeps its own mode, and gets
  15 only if it sets none. Found by the PDF → DOCX Word read-back (`benchmarks.pmc
  word`): all 66 development-corpus documents opened in mode 14.

- **A DOCX template keeps its own body font, and `.dotx` templates are accepted.**
  The renderer set the Normal style to Calibri 11 on every render, so a template's
  Georgia 12 came out as Calibri 11, the very styling the template was passed for.
  `default_font` and `default_font_size` now default to unset: a blank document still
  gets Calibri 11, a template keeps its own, and a font you name still wins. A Word
  template (`.dotx`) passed as `template_path` was refused with "is not a Word file";
  it is now read as a template.

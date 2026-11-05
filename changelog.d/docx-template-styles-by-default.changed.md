- **Breaking: a DOCX template now gives you its styles, not its text.** With `--template-docx`, the new
  short name for `--docx-renderer-template-path` (`template_path`), the output uses the template's styles,
  page setup, headers and footers, and leaves out its body text: `clear_template_body` now defaults to
  `True`. If your template's text belongs in every document, such as a letterhead or a cover page, add the
  new `--docx-renderer-no-clear-template-body` (`clear_template_body=False`), or that text will silently
  disappear from your output. `--docx-renderer-clear-template-body` still works but is no longer needed.

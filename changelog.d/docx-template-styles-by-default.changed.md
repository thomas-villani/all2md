- **Breaking: a DOCX template now gives you its styles, not its text.** With
  `--docx-renderer-template-path` (`template_path`), the output uses the template's styles, page setup,
  headers and footers, and leaves out its body text. If your template's text belongs in every document,
  such as a letterhead or a cover page, add the new `--docx-renderer-keep-template-body`
  (`keep_template_body=True`), or that text will silently disappear from your output.

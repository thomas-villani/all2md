- **PDF footnotes become real footnotes.** A page's notes below Word's short separator rule
  (at the left margin, low on the page, set smaller than the body, each opened by a small or
  raised label) now become footnote definitions, and the raised numbers in the text that
  match them become footnote references, so Markdown gets `[^1]` and Word gets real
  footnotes. Before, the note text stayed at the foot of each page in the body, and each
  reference number was glued to the word before it ("Rules1"). A note continued onto the
  next page is joined to its start. Text under a short rule that carries no labels (a
  signature line) is left alone. On 755 Word documents made into PDFs by Word, 86% of the
  footnotes come through, against 61% for Word's own PDF import. Turn it off with
  `--no-detect-footnotes` (`PdfOptions.detect_footnotes`).

- **DOCX: comments keep their words together, and a thread keeps its shape.** A comment's
  text was joined with a space at every run boundary (`Recon sider  this`) and its
  paragraph breaks were lost. Each comment now records the text it is anchored to, the
  comment it replies to, and whether its thread is resolved (`anchored_text`,
  `parent_label` and `resolved` metadata), and the Markdown renderer prints them in the
  comment header, e.g. `Reply comment2 to comment1 by Bob` and `[resolved] on "the text"`.

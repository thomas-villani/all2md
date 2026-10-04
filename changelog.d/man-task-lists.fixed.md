- **Man page task items read back as tasks.** man has no checkboxes, so the man
  renderer writes a task item as `[ ] text` or `[x] text`. The parser now reads a
  leading `[ ]`, `[x]` or `[X]` marker on a list item as its task status, as
  GitHub-flavored Markdown does, so `- [x] done` survives a man round trip instead of
  coming back as the literal text `\[x\] done`.

- **Markdown: a paragraph beginning with `- ` or `+ ` no longer reparses as a list.** The
  renderer already escaped the other list openers — `*` everywhere it appears, and an
  ordered marker such as `03)` or `1.` since #499 — but the two remaining bullet
  characters were left bare, so a paragraph reading "- 5 degrees below" or "+ tax
  included" came back from its own output as a one-item bullet list. Any source can
  produce such a paragraph: DOCX, PDF, HTML and hand-written prose alike.

  A marker is escaped only at a paragraph's start and only when a space or the end of the
  text follows it, which is what leaves `-5`, `+44` and a mid-sentence dash untouched. A
  thematic break is a different node and still renders as `---`.
  ([#502](https://github.com/thomas-villani/all2md/issues/502))

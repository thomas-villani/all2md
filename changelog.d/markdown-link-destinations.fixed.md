- **markdown: a link or image whose URL holds a space, an unmatched parenthesis or a
  line break is written so it reads back.** The renderer wrote every URL bare, as
  `[text](url)`, so `file:///C:/My Docs/a.pdf` read back as plain text and
  `https://example.com/x)y` as a link cut short at the `)`. Such a URL is now written in
  the pointed form `[text](<url>)`, line breaks and control characters are
  percent-encoded, and a backslash that would escape the next character is doubled. The
  same applies to images and reference definitions. A title holding a `"` is escaped
  instead of ending the title early.

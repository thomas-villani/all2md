- **Man page lists with nested lists stay tight.** A list item holding a nested list
  (`.IP` text followed by `.RS` … `.RE`) made the whole list loose, so `- a` with
  `  - b` written to a man page and read back gained a blank line between every
  item. A nested list no longer loosens its item; a second paragraph or a code
  block still does.

- **Content without a filename is detected better: HTML fragments are HTML, and a
  `#` comment alone is not TOML.** `echo "<p>V1</p>" | all2md -` printed the tags as
  plain text, because only a whole page (`<!DOCTYPE html>`, `<html>`) was recognized;
  content that opens with an HTML element and closes it is now read as HTML, asked
  last so a Markdown README that opens with `<p align="center">` stays Markdown. And
  `echo "# Test" | all2md -` came back in a TOML code block, since comments alone are
  a valid, empty TOML document; TOML now needs at least one key.

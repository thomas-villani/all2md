- **AsciiDoc admonitions are admonitions everywhere, in all three of their forms.** The
  AsciiDoc parser marked `[NOTE]` with a `role`, where the RST and MkDocs parsers write
  `admonition_type` and `admonition_title`, so an AsciiDoc note or warning reached every
  other format as a plain quote with its label gone. It now writes the same keys (the
  contract is documented on `BlockQuote`), and it reads the two forms it used to miss:
  the paragraph form `NOTE: text`, which most AsciiDoc uses and which was read as an
  ordinary paragraph with "NOTE:" in it, and `[WARNING]` above a `====` block, which was
  read as an example block. A `.Title` above an admonition, before or after the label,
  becomes its title. The Markdown renderer now labels an admonition from any source
  (`> **Warning:** ...`), not only RST and MkDocs ones, and on a flavor with admonitions
  (`markdown_plus`) writes every one natively as `!!! warning`.

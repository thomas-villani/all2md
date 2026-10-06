- **`--extract` takes a section's subsections with it.** Extracting `Introduction`
  stopped at the next heading of any level, so a section that opens with a
  subheading came back as its heading alone. A section now runs to the next heading
  at its level or above, in `--extract` (with or without `--line-numbers`), in
  `extract_sections()` and in the MCP tools that use it. Selecting a section together
  with one of its own subsections (`#:2-3`) no longer repeats the subsection.

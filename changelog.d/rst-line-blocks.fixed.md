- **reST line blocks are no longer silently dropped.** A `| ` line block fell
  through the parser's unknown-node branch, so every line of it vanished from
  the output -- text loss, not formatting loss. A line block now parses as a
  paragraph whose lines join with hard breaks; nested (indented) lines flatten
  into the same paragraph, since the AST does not model their indentation.

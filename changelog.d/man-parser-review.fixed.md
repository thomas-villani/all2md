- **Three man page parser edge cases.** `.ig XX` now skips up to `.XX`, as roff does,
  instead of stopping at the first `..` and printing the rest of the ignored block.
  Numeric character references outside Unicode (`\[u110000]`, `\[char1114112]`,
  `\N'99999999'`), surrogates (`\[uD800]`) and `\N'…'` with a non-ASCII digit raised an
  unhandled error; they now read as U+FFFD. The NAME section's description keeps
  formatted words: `foo \- list \fBall\fR files` gave "list  files".

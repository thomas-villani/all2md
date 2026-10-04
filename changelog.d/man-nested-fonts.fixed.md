- **Man pages keep nested bold and italic.** `\fBbold with \f(BIitalic\fB inside\fR`
  came back as three siblings (bold, bold-italic, bold), so `**bold with *italic*
  inside**` written to a man page and read back lost its nesting. Font runs are now
  nested: the longest bold or italic stretch becomes the outer node, with italic
  outside on a tie as CommonMark nests `***x***`. Constant width inside bold or italic
  (`\f(CB`, `\f(CI`, `\f[CBI]`) is now read as code inside that formatting instead of
  dropping it.

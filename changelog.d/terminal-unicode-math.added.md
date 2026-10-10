- **Math in the terminal can be shown as Unicode text.** `--math unicode` (for `rcat`,
  `--rich` and `all2md read`; `TerminalRendererOptions.math_mode`, `ALL2MD_MATH`, `math`
  in the `[read]` config section) writes formulas with Unicode symbols, superscripts and
  subscripts instead of their LaTeX source: `\alpha^2 + x_i` reads `α² + xᵢ` and
  `\frac{a+b}{2}` reads `(a+b)/2`. Display math lays out the rows of `aligned`, `cases` and
  matrices on lines of their own, with tall brackets around a matrix. Nothing is dropped: a
  character Unicode cannot raise or lower keeps its `^` or `_`, and an unknown macro is
  kept as written. It needs `pylatexenc` (the `latex` extra); `latex` stays the default.

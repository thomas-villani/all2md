- **Word equations read back as the LaTeX they are.** The DOCX parser read fractions,
  scripts and roots, but flattened the rest: brackets, matrices, `cases`, accents, bars,
  braces, named functions and limits lost their structure, and every sum or integral read
  as `\sum`, because the operator's character was looked for in the wrong place (an
  `m:nary` with none is an integral). Each OMML structure Word builds now has its LaTeX:
  `\left(`...`\right)` around a tall group and plain brackets otherwise, `pmatrix` and
  its siblings by bracket, `cases`, `aligned` or `gathered` equation arrays, `\binom`,
  `\hat`/`\widehat` and the other accents, `\overline`, `\underbrace{...}_{...}`,
  `\sin x`, `\lim_{x \to 0}`, `\operatorname`, `\boxed`, `\text`, and font styles
  (`\mathbf`, `\mathbb`, ...). Symbols are written as macros (`\alpha`, `\le`, `\to`)
  rather than left as Unicode, which LaTeX does not read in math, so `±` is now `\pm`.
  Equations the DOCX renderer writes come back unchanged.

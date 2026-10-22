- **Math in DOCX output is a Word equation.** The DOCX renderer wrote inline math as its
  LaTeX source between `$` signs and display math as a code block, so Markdown with math
  arrived in Word as source code. It now writes Office Math (OMML), which Word's equation
  tools edit: scripts, fractions and binomials, roots, accents, bars and braces, sums,
  products and integrals with their limits, named functions (`\sin`, `\lim_{x \to 0}`),
  `\left`/`\middle`/`\right` delimiters, matrices, `cases`, rows aligned at `&`, font
  styles (`\mathbf`, `\mathbb`, ...) and `\text`. A macro it does not know stays in the
  equation as written. The new `math_mode` option (`--docx-renderer-math-mode`) is
  `native` by default; `latex` keeps the old output. The `docx` extra now installs
  `pylatexenc`, which reads the LaTeX; without it, and for a formula that does not parse,
  the source is written as before.

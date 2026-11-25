- **`--math unicode` no longer drops or misplaces parts of a formula.**
  `\displaystyle` took the next symbol as its argument and deleted it, so
  `\displaystyle \sum_k a_k` lost its `∑`. A script inside a script that Unicode cannot
  raise went bare, so `2^{2^n}` read as `(2²)ⁿ`; it is now `2^(2ⁿ)`, and two symbols
  (`e^{i\pi}`) take parentheses too. `\overbrace{a+b}^{n}` put the label on `b` alone and
  is now `(a+b ⏞ n)`; `\boxed{x = 2}` is `⟦x = 2⟧`, no longer the Iverson bracket
  `[x = 2]`; `\operatorname*` no longer leaks its star, and `\not\equiv b` keeps its
  space.
- **Macros `--math unicode` left as LaTeX are now written out.** The logic symbols
  (`\implies`, `\iff`, `\land`, `\lor`, `\neg`, `\bot`, `\models`), `\|`, `\ne`, `\Re`,
  `\Im`, `\qed` and some forty more that pylatexenc does not name; the DOCX equation
  writer takes the same table, so Word no longer gets them as text either.
  `\stackrel`, `\overset` and `\underset` become a script (`=ᵈᵉᶠ`, `arg maxₓ`), as do the
  labels of `\xrightarrow` and its kin; `\substack` rows share one script
  (`∑_(p ≤ x; p ≡ 1 mod 4)`); `{a \over b}` and `{n \choose k}` are a fraction and a
  binomial. `\color`, `\colorbox`, `\phantom`, `\hspace`, `\hline` and the struts are
  shown as what they leave behind, and `\cancel` strikes its argument through.
- **`--math unicode` reads closer to typeset math.** `\mathbf`, `\boldsymbol` and `\bm`
  use Unicode's mathematical bold letters (`𝐯`, `𝜶`) and `\mathbb{1}` is `𝟙`, as
  `\mathbb{R}` already was `ℝ`. A differential or a factorial is one term in a fraction
  (`∂²f/∂x∂y`, `d²y/dx²`, `xⁿ/n!`, not `(∂ x ∂ y)` or `(n!)`). `45^\circ` is `45°`,
  `A^\top` is `Aᵀ` and `x^\prime` is `x′`. No space is left inside `⟨x, y⟩`, `⌊x⌋`,
  `\left\| x \right\|` or `\lvert y \rvert`, and the space `\text{ if }` keeps replaces
  the math space beside it instead of doubling it (`if x`, not `if  x`), so a `\quad`
  is two spaces.

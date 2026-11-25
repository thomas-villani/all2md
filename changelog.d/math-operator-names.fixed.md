- **`--math unicode` names `\gcd`, `\lcm`, `\deg`, `\det`, `\ker` and the other named
  functions, and writes `\bmod`, `\mod` and `\pod`.** pylatexenc, which supplies the
  symbols, knows only some of LaTeX's named functions, so `\gcd(a,b)` reached the terminal
  as written; `\arg`, `\dim`, `\hom`, `\ker`, `\lg`, `\Pr`, `\cot`, `\sec` and `\csc` did
  too. The terminal renderer now names all of them itself, with the table the DOCX
  equation writer already used, which gains `lcm` (not LaTeX's, but defined so often that
  a formula using it means the function). `a \bmod n` is `a mod n`, `\mod{n}` is `mod n`
  and `\pod{n}` is `(n)`, beside the `(mod n)` that `\pmod` already gave; the DOCX writer
  makes the same three upright `mod` runs instead of writing the macro as text.
- **A subscript containing words keeps its `_`.** The space inside `\text{ prime}` was
  squeezed out with the math spaces, so `\prod_{p \text{ prime}}` read as `∏ₚₚᵣᵢₘₑ`; it is
  now `∏_(p prime)`, as `\sum_{i \in S}` is `∑_(i ∈ S)`. A single word still drops to
  subscript letters (`x_{\text{max}}` is `xₘₐₓ`).

# Kitchen Sink

A document that combines many constructs so we can catch bad *interactions*
between them, not just each one in isolation.

## Prose and inline

A paragraph with *emphasis*, **strong**, `code`, ~~strikethrough~~, a
[link](https://example.com), and a footnote reference.[^note] It also soft-wraps
across
two lines.

## A loose list with mixed content

1. First item with a paragraph.

   And a second paragraph, plus a nested list:

   - nested bullet with a `code` span
   - nested bullet with **strong** text
2. Second item containing a table:

   | Key | Value |
   |:----|------:|
   | a   | 1     |
   | b   | 2     |
3. [ ] Third item is an unchecked task that wraps
   onto a continuation line

## A blockquote with structure

> A quoted paragraph introducing math: $a^2 + b^2 = c^2$.
>
> > A nested quote with a fenced block:
> >
> > ```python
> > print("nested")
> > ```

## Definitions and math

Term
:   A definition with a [link](https://example.org) and *emphasis*.

$$
\int_0^1 x^2 \, dx = \frac{1}{3}
$$

---

The closing paragraph after a thematic break.

[^note]: The footnote definition, with a second paragraph.

    This paragraph must not collapse into the first.

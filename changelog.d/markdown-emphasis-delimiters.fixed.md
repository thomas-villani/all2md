- **markdown: emphasis and strong delimiters are written so they close (#529).** Three
  shapes came back as literal stars:
  - **Whitespace at a span's edge.** `Strong("bold ")` then `"after"` was written
    `**bold **after`, and a `**` next to a space does not delimit. Whitespace at either
    edge of an emphasis, strong or strikethrough span now goes outside it:
    `**bold** after`.
  - **Neighbor spans sharing a style.** `Emphasis[Strong("Meta")]` then
    `Strong("-analysis")` was written `***Meta*****-analysis**`, and the five stars
    read as one run. Neighbor runs are now merged so each style opens once:
    `***Meta*-analysis**`. An emphasis nested in an emphasis is no longer written `**x**`,
    which read as strong.
  - **Crossing spans.** Where one span closes and another opens with no shared style
    (`**x *a***` then `*b*`), the second is written with `_` (`_b_`).

  A style change in the middle of a word, with no space, still cannot always be
  written: CommonMark reads `***a*b*c***` and `*q.*a` differently from what was meant.

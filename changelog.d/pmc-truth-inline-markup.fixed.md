- **The PMC born-digital ground truth no longer prints a space where the page prints
  none.** The JATS projection joined every element's text with a space so that
  `<label>Table 2</label>` could not fuse onto the caption after it. Structural
  boundaries do need that space; inline ones do not, and JATS marks up part of a word
  constantly -- `bla<sub>CTX-M</sub>` is printed `blaCTX-M`, `T<sub>a</sub>` is `Ta`,
  `et al.<sup>12</sup>` is `et al.12`, `VAS 1<sup>st</sup> week` is `VAS 1st week`.
  Every such boundary put five n-grams of ground truth beyond the reach of any
  converter, all2md included, and the tables carry the most of them. The projection now
  renders an element as the page prints it: the source's own whitespace inside a line,
  a space only at a structural boundary. The set of inline elements is measured, not
  assumed -- across both development corpora these are the tags whose text abuts a
  neighbour with no whitespace in the source, `xref` 22,934 times down to the tens --
  and anything unrecognised keeps its space, because a missing space fuses two words
  into a token nothing can match while a spurious one only splits them.

  Measured on the recorded table replay over the two development corpora, correcting
  the truth alone moves mean n-gram containment from 0.814 to 0.843 (66-article dev)
  and 0.804 to 0.839 (110-article tuned), with 38 of the 41 tables that move getting
  better; several tables that scored 0.1 to 0.7 were in fact reproduced whole. For
  comparison, an oracle that cuts every recorded grid's columns at the best position --
  a perfect fix for tables the detector fuses side by side -- is worth 0.004 and 0.013
  on the same corpora, so the artifact was larger than the defect it was hiding. About
  3% of the ground truth's prose 5-grams are affected too. `benchmarks/pmc/reference.json`
  and every published figure drawn from it are re-recorded against the corrected
  projection in the same release.

- **`block_structure_similarity` no longer scores content-free output 1.0, and no longer
  reads as a block-count ratio.** The benchmark dimension compared the two block-kind
  sequences by edit distance and never looked at the text under a block, so one block of
  anything on a one-block page scored a perfect 1.0 — one slide reproducing 7% of its text
  did. And because an edit distance is at least the length difference, the score could
  never exceed the ratio of the two block counts: OmniDocBench annotates a whole list as one
  region where all2md emits a block per item, so most of what it measured was two
  definitions of a block disagreeing. Each block is now located in the other side's text
  and must clear the identification floor reading order adopted in #246 — half its
  characters aligned — before its kind counts; its aligned characters vote for the kind of
  the block they landed in, and the score is the F1 of kinds matched in both directions.
  Splitting or merging blocks of one kind is free; a title emitted as body text, or a table
  recovered as a paragraph, is still charged. Display equations carry no text to locate and
  are left to the formula dimensions. The OmniDocBench oracle schema moves to 8 with a
  re-recorded baseline, and the PMC lane's oracle version to 4. The dimension stays ungated
  in both lanes until it has been measured against the wrong-page and mutation controls.
  The PMC lane's mutation controls also pair each kind with its own text past a display
  equation, which they previously misaligned.
  ([#256](https://github.com/thomas-villani/all2md/issues/256))

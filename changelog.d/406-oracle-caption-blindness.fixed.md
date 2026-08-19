- **Benchmark oracle: bound captions count as text again** (#406). The shared AST
  projection read children only, so a caption the parser correctly bound to
  `Figure.caption`/`Table.caption`/`Image.caption` vanished from measurement — recall
  *fell* as figure binding improved, and 101 of the 103 "lost" captions on the held-out
  corpus were in the output the whole time. Captions now project as text blocks on both
  lanes (PMC schema 6, OmniDocBench oracle schema 6), and both evidence artifacts are
  re-recorded against the corrected instrument.

- **benchmarks/omnidocbench: oracle schema version 6 → 7, with a re-recorded baseline.**
  #443 widened `_semantic_blocks` to admit any container of inline text, which changes what
  the AST-side projection can see. The version was deliberately held at 6 at the time,
  because the widening provably cannot reach this lane — it projects the PDF parser's AST,
  which emits no definition lists and wraps every list item in a `Paragraph`, and 8 of 8
  sampled corpus PDFs projected byte-identically across the change. It moves now because a
  baseline has been re-recorded alongside it, which is the only way it may move: the gate
  compares this constant against the version its `baseline.json` carries, so changing one
  without the other reports identity drift instead of a fidelity result.

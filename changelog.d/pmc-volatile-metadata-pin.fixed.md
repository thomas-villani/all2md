- **benchmarks/pmc: a rewritten PMC housekeeping timestamp no longer fails the corpus
  pin.** The born-digital corpus pins every article by the SHA-256 of its bytes, and PMC
  rewrites a `pmc-last-change` timestamp in place — moving the digest while leaving every
  word of prose, every table and every reference untouched. The scheduled run on
  2026-09-15 aborted on exactly that: same byte count, different digest, and normalising
  the one element away made the files identical.

  Each manifest row now carries a second `xml_content_sha256`, taken with that element
  removed, and the manifest schema moves to 2. A byte mismatch is tolerated **only** when
  the content digest still agrees; the article is then named in
  `CorpusSnapshot.tolerated_drift` and in the recorded provenance, so a reading states
  whether it scored the pinned bytes or bytes accepted under tolerance. That payload
  change bumps the lane's schema to 8, which is why the reference artifact is re-recorded
  alongside it.

  The tolerance is deliberately one named element wide. Sweeping all 279 pinned articles
  found 14 drifted: 13 were the timestamp alone, and one was a real change — a DOI
  corrected to its full page-range form in a reference list — which still fails, because
  blessing it silently is the failure mode the pin exists to prevent. No PDF drifted at
  all.

  Each manifest records the digest it supersedes, so the pins cited by already-published
  readings stay traceable. Content digests were computed from verified pinned bytes for
  the development and tuned corpora; for seven articles in the held-out corpus no pinned
  copy survives locally, so theirs were taken from the served bytes and are listed in that
  manifest as inferred rather than passed off as verified.
  ([#509](https://github.com/thomas-villani/all2md/issues/509))

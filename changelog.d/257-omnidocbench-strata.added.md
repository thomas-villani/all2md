- **OmniDocBench lane: per-data-source strata** (#257). The scanned-page payload now
  reports every dimension per corpus stratum (newspapers, notes, slides, textbooks,
  papers, …) alongside the whole-corpus mean, which could not say *where* a score was
  earned or lost. Strata are evidence, not identity: the gate does not compare them and
  a baseline never copies them.

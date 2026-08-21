- **The Semgrep gate now scans `benchmarks/` as well as `src/`** (#328). The first
  working run of the gate (#325) scoped it to `src/` and parked 16 findings outside
  shipped code for triage. Triaged: the two benchmark corpus fetchers already parse
  third-party XML through `defusedxml`; their one remaining `urlopen` against a fixed
  https host and the annotation-only `xml.etree` import carry per-line suppressions
  with the reasoning beside them. `tests/` and `stubs/` are excluded in
  `.semgrepignore` -- the findings there are audit-rule hits on localhost test
  servers, fixture XML and a content-hash MD5, none of which ships or sees untrusted
  input -- with the exclusion documented next to the entry rather than as eleven
  inline comments. The scan is widened to the repository root and verified clean.

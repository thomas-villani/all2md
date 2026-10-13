- **Releases publish the files CI tested, and every publish path checks CI.** A new
  CI job builds the sdist and wheel once, runs `twine check --strict`, installs the
  wheel alone into a clean environment and smoke-tests it (bare, then with
  `[markdown,docx]`), audits the resolved dependencies with `pip-audit` (blocking on
  release tags), and uploads the result; `release.yml` publishes that artifact rather
  than rebuilding. Publishes from a UI-made release or a manual dispatch now refuse a
  commit without a successful CI run. The release job also requires the quality-gate,
  format-benchmark and package jobs, and fails while the latest scheduled corpus,
  DOCX ledger or OmniDocBench run is red. The PyPI publish action is pinned to a
  commit, and changelog fragments are checked on every PR.

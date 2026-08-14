- **Changelog entries are now written as `changelog.d/` fragments, not as edits to
  `CHANGELOG.md`.** Every branch appended its entry to the same place in the same
  file — under `## [Unreleased]`, at the end of the same `###` section — so any sweep
  landing more than one PR hit a conflict in `CHANGELOG.md` on every merge after the
  first, and resolving it by hand next to two thousand lines of prose is exactly the
  situation in which an entry gets dropped. A PR now adds
  `changelog.d/<slug>.<category>.md` holding the bullets it wants published; two
  branches never write the same lines because they never write the same file.
  `scripts/compile_changelog.py --version X.Y.Z` folds the fragments into a new
  released section at release time, updates the link references at the bottom of the
  changelog, and deletes what it consumed; `--check` validates fragments without
  writing. Entries already sitting under `## [Unreleased]` were deliberately left
  there rather than migrated: the compiler merges hand-written content and fragments
  into the same sections by design, so the two styles coexist and nothing had to be
  rewritten to adopt this. towncrier and scriv were both rejected — they rewrite the
  whole changelog with their own newline and formatting conventions, which would turn
  a two-line release edit into a whole-file diff and flatten the long-form entries
  this project writes. Nothing enforces the fragment yet; adding a CI check that a PR
  touching `src/` carries one is a separate decision.

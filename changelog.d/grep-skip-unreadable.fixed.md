- **`grep` and `search` skip a file they cannot read and search the rest.** One file in a
  folder whose format needed a missing optional dependency (a `.chm` without pychm, say),
  or that was damaged or encrypted, ended a recursive `all2md grep` with exit 2 and no
  results at all. Like `grep`, both commands now print `all2md grep: FILE: skipped: REASON`
  on stderr for that file and search the others. A run in which every input fails still
  fails as before. `SearchService.build_indexes(..., skip_errors=True)` does the same for
  the Python API and records what it left out in `service.skipped`; its default is
  unchanged.

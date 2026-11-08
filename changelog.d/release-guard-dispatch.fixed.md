- **A re-run fidelity lane now clears a stale failure before release.** The release job
  read only the latest *scheduled* run of the corpus, DOCX ledger, OmniDocBench and PMC
  lanes, so a monthly lane that failed on the 1st blocked every tag until the next month,
  even after the fix was merged and a manual run on `main` passed. It now reads the
  newest finished run on `main`, scheduled or dispatched, and prints its commit.
  Runs on other branches, cancelled runs and dispatches that do not gate (baseline
  recordings, PMC subsets or other layout modes, now titled `[not a gate]`) are not
  counted.

- **The PMC lane can score under a chosen layout mode.** `benchmarks.pmc score
  --layout-mode {enabled,disabled,auto}`, and a `layout_mode` input on the workflow's
  manual dispatch, convert the corpus under that `layout_analysis_mode` and record it in
  the payload's `parser_config`. The lane's policy, its scheduled runs and
  `reference.json` stay `enabled`; the other modes measure what layout analysis is worth,
  which PyMuPDF 2.0 makes the question behind what `auto` should mean.

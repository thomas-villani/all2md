- **CI gates per-format throughput, relative to the rest of the run.** A new
  `Throughput Gate` job runs the `tests/performance` suite twice and fails when one
  format is more than 30% slower than `benchmarks/throughput_baseline.json` *relative
  to the median of the other formats in the same pass*, in both passes. A variance
  study of 1,003 CI runs set the design: the ubuntu-latest pool has CPU classes about
  0.57x, 0.73x and 1.0x apart that move every format at once, so raw time cannot be
  gated, while relative to the run each format's noise is 1.5-4% and no CPU class
  shifts it by more than 9%. On those runs the gate caught an injected 1.5x slowdown
  of one format 99% of the time and 2x every time, raised no false alarm, and would
  have gone red on the 1.35-1.4x PDF slowdown that #380/#381 shipped in August. It
  cannot see a slowdown shared by every format, which looks the same as a slower
  runner. It blocks merges and releases; a deliberate slowdown re-records the
  baseline in the same PR (the job comment in `ci.yml` has the two commands).
  ([#183](https://github.com/thomas-villani/all2md/issues/183))

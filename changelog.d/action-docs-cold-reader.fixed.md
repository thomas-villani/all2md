- **The GitHub Action's Quick Start workflow works as written.** It set
  `report-fail-under` on Markdown files, which have no confidence detector, so the gate
  refused the run with exit code `2` (it refuses any threshold that could only ever pass).
  The docs now gate Markdown on round-trip fidelity alone, show the confidence check
  separately for PDFs, and explain both scores before the first example. The README
  links to the action from its header.
  ([#186](https://github.com/thomas-villani/all2md/issues/186))

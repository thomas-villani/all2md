"""Markdown roundtrip fidelity benchmark for all2md.

Where ``benchmarks/corpus/`` times *to-markdown* conversion and
``benchmarks/startup.py`` times cold start, this package measures **Markdown-in
roundtrip fidelity**: does ``Markdown -> AST -> Markdown`` preserve the document?

Two independent oracles judge each case (see ``oracles.py``):

- **idempotency** - render twice, assert the output is a fixed point. Cheap,
  deterministic, and the exact criterion the recent list/footnote roundtrip
  fixes (#84/#85/#91) were validated against.
- **html_equivalence** - render the original and the roundtripped Markdown both
  to HTML with a fixed reference renderer (mistune) and diff. Independent of
  all2md's own AST model and Markdown renderer - the two surfaces where losses
  actually occur - so it catches first-render loss idempotency can't see.

The corpus (see ``corpus.py``) is synthetic Markdown authored to exercise the
full construct matrix all2md supports, including the extensions the CommonMark /
GFM spec suites don't cover (footnotes, definition lists, math, admonitions,
mark/insert/super/subscript) and the specific shapes behind #84/#85/#91.

Run it::

    python -m benchmarks.roundtrip            # table to stdout
    python -m benchmarks.roundtrip --json out.json
    python -m benchmarks.roundtrip --show-diff   # print diffs for failures
"""

from __future__ import annotations

from .corpus import Case, load_synthetic_corpus
from .oracles import CheckResult, html_equivalence_check, idempotency_check

__all__ = [
    "Case",
    "CheckResult",
    "html_equivalence_check",
    "idempotency_check",
    "load_synthetic_corpus",
]

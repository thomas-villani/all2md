"""Entry point for ``python -m benchmarks.roundtrip``."""

from __future__ import annotations

import sys

from .run import main

if __name__ == "__main__":
    sys.exit(main())

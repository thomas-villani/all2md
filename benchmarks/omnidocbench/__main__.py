"""CLI entry point for ``python -m benchmarks.omnidocbench``."""

import sys

from .run import main

if __name__ == "__main__":
    sys.exit(main())

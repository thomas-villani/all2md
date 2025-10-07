#!/usr/bin/env python3
"""Entry point for running all2md as a module.

This allows the package to be executed as:
    python -m all2md [arguments]
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

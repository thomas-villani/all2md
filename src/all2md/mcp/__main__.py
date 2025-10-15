#!/usr/bin/env python3
#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/mcp/__main__.py

"""Entry point for running all2md-mcp as a module.

This allows the package to be executed as:
    python -m all2md.mcp [arguments]
"""

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())

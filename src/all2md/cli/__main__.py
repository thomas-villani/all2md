#!/usr/bin/env python3
"""Entry point for running the CLI package as a module.

This allows the CLI to be executed as:
    python -m all2md.cli [arguments]

``python -m all2md`` already worked; this package did not, and the failure was
worse than a plain "no such command". Python reports ``No module named
all2md.cli.__main__; 'all2md.cli' is a package and cannot be directly executed``
and exits *before* argparse ever sees the arguments, so every invocation fails
identically no matter what follows it. A script checking whether a flag is
accepted therefore gets the same answer for a real flag and an invented one.
"""

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())

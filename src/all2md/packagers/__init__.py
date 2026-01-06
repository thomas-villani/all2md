#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/packagers/__init__.py
"""Packagers for generating submission-ready document packages.

This module provides packagers that create complete submission packages
for academic publishers and preprint servers.

Available packagers:
- ArxivPackager: Generate ArXiv-ready LaTeX submission packages

"""

from __future__ import annotations

from all2md.packagers.arxiv import ArxivPackageOptions, ArxivPackager

__all__ = [
    "ArxivPackager",
    "ArxivPackageOptions",
]

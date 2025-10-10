#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/__init__.py
"""Converters package initialization.

This package contains converter modules for various document formats.
Each converter module contains a CONVERTER_METADATA object that describes
the converter and enables automatic registration via the registry's
auto-discovery mechanism.

New parsers can be added by simply creating a new module in this directory
with a CONVERTER_METADATA object - no manual registration required.
"""

from all2md.converter_registry import registry

# Trigger auto-discovery of all converter modules
# This will scan the parsers directory and register all modules
# that contain a CONVERTER_METADATA object
registry.auto_discover()

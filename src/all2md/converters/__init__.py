#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# src/all2md/converters/__init__.py
"""Converters package initialization.

This package contains converter modules for various document formats.
Each converter module contains a CONVERTER_METADATA object that describes
the converter and enables automatic registration via the registry's
auto-discovery mechanism.

New converters can be added by simply creating a new module in this directory
with a CONVERTER_METADATA object - no manual registration required.
"""

from all2md.converter_registry import registry

# Trigger auto-discovery of all converter modules
# This will scan the converters directory and register all modules
# that contain a CONVERTER_METADATA object
registry.auto_discover()

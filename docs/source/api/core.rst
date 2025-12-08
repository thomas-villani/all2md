Core API
========

The core API provides the main entry points for document conversion. These functions
handle format detection, parsing, transformation, and rendering in a unified interface.

Main Functions
--------------

The primary functions for document conversion:

.. autosummary::
   :nosignatures:

   all2md.to_markdown
   all2md.to_ast
   all2md.from_ast
   all2md.from_markdown
   all2md.convert

For full function signatures and detailed documentation, see :doc:`all2md.api`.

Base Classes
------------

Parser and renderer base classes define the interface that all format handlers implement:

.. autosummary::
   :nosignatures:

   all2md.options.base.BaseParserOptions
   all2md.options.base.BaseRendererOptions
   all2md.parsers.base.BaseParser
   all2md.renderers.base.BaseRenderer

Common Options
--------------

Shared option classes used across multiple formats for network and file access:

.. autosummary::
   :nosignatures:

   all2md.options.common.NetworkFetchOptions
   all2md.options.common.LocalFileAccessOptions

Exceptions
----------

The exception hierarchy for handling conversion errors:

.. autosummary::
   :nosignatures:

   all2md.exceptions.All2MdError
   all2md.exceptions.ValidationError
   all2md.exceptions.FileError
   all2md.exceptions.FormatError
   all2md.exceptions.ParsingError
   all2md.exceptions.RenderingError
   all2md.exceptions.TransformError
   all2md.exceptions.SecurityError
   all2md.exceptions.DependencyError

Progress Reporting
------------------

Classes for tracking conversion progress:

.. autosummary::
   :nosignatures:

   all2md.progress.ProgressEvent
   all2md.progress.ProgressCallback

Converter Registry
------------------

The registry system for format detection and converter lookup:

.. autosummary::
   :nosignatures:

   all2md.converter_registry.ConverterRegistry
   all2md.converter_metadata.ConverterMetadata

Detailed Module Reference
-------------------------

.. toctree::
   :maxdepth: 1

   all2md
   all2md.api
   all2md.constants
   all2md.exceptions
   all2md.converter_registry
   all2md.converter_metadata
   all2md.progress
   all2md.options.base
   all2md.options.common

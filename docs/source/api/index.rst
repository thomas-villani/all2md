API Reference
=============

This section provides comprehensive API documentation for the all2md library.
The API is organized into logical sections based on functionality.

Quick Links
-----------

.. list-table::
   :widths: 25 75
   :header-rows: 0

   * - :doc:`core`
     - Main entry points: ``to_markdown()``, ``to_ast()``, ``from_ast()``, ``convert()``
   * - :doc:`parsers`
     - Format-specific parsers (PDF, DOCX, HTML, and 35+ more)
   * - :doc:`renderers`
     - Output renderers (Markdown, HTML, DOCX, PDF, and 20+ more)
   * - :doc:`transforms`
     - AST transformation pipeline and built-in transforms
   * - :doc:`cli`
     - Command-line interface components
   * - :doc:`utilities`
     - Internal utilities for input handling, images, and security
   * - :doc:`advanced`
     - AST nodes, search, diffing, and MCP integration

.. toctree::
   :maxdepth: 2
   :caption: API Sections

   core
   parsers
   renderers
   transforms
   cli
   utilities
   advanced

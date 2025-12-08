Utilities
=========

The utilities package provides shared functionality used across parsers and renderers.
These modules are primarily internal but may be useful for advanced customization.

Input Handling
--------------

Modules for loading and processing input sources:

.. autosummary::
   :nosignatures:

   all2md.utils.input_sources
   all2md.utils.inputs
   all2md.utils.encoding
   all2md.utils.io_utils

Content Processing
------------------

Text and HTML processing utilities:

.. autosummary::
   :nosignatures:

   all2md.utils.text
   all2md.utils.html_utils
   all2md.utils.html_sanitizer
   all2md.utils.escape
   all2md.utils.parser_helpers

Attachments & Images
--------------------

Image handling and attachment processing:

.. autosummary::
   :nosignatures:

   all2md.utils.attachments
   all2md.utils.images

Security
--------

Security utilities for network and file access:

.. autosummary::
   :nosignatures:

   all2md.utils.security
   all2md.utils.network_security

Format-Specific Helpers
-----------------------

Utilities for specific format handling:

.. autosummary::
   :nosignatures:

   all2md.utils.spreadsheet
   all2md.utils.chart_helpers
   all2md.utils.footnotes
   all2md.utils.flavors

Other Utilities
---------------

Additional utility modules:

.. autosummary::
   :nosignatures:

   all2md.utils.metadata
   all2md.utils.packages
   all2md.utils.decorators
   all2md.utils.static_site

Complete Utilities Reference
----------------------------

.. toctree::
   :maxdepth: 1

   all2md.utils

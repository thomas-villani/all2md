CLI Module
==========

The CLI module provides the ``all2md`` command-line interface. While most users
interact with the CLI directly via the terminal, these modules can also be used
programmatically for building custom tools.

For user-facing CLI documentation, see :doc:`/cli`.

Main Components
---------------

Core CLI functionality:

.. autosummary::
   :nosignatures:

   all2md.cli.builder
   all2md.cli.processors
   all2md.cli.validation

Commands
--------

CLI subcommands for various operations:

.. autosummary::
   :nosignatures:

   all2md.cli.commands

Configuration
-------------

CLI configuration and preset management:

.. autosummary::
   :nosignatures:

   all2md.cli.config
   all2md.cli.presets

Input/Output
------------

Input handling and output formatting:

.. autosummary::
   :nosignatures:

   all2md.cli.input_items
   all2md.cli.output
   all2md.cli.progress

Additional Modules
------------------

Supporting functionality:

.. autosummary::
   :nosignatures:

   all2md.cli.watch
   all2md.cli.timing
   all2md.cli.help_formatter
   all2md.cli.custom_actions
   all2md.cli.packaging

Complete CLI Reference
----------------------

.. toctree::
   :maxdepth: 1

   all2md.cli
   all2md.cli.commands

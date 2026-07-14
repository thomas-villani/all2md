Advanced Modules
================

These modules provide advanced functionality for working with document ASTs,
search indexing, document comparison, and LLM integration.

AST (Abstract Syntax Tree)
--------------------------

The AST module defines the document structure used internally by all2md. All parsers
produce AST documents, and all renderers consume them.

For user-facing AST documentation, see :doc:`/ast_guide`.

Core Classes
^^^^^^^^^^^^

.. autosummary::
   :nosignatures:

   all2md.ast.nodes.Document
   all2md.ast.nodes.Node
   all2md.ast.builder.DocumentBuilder
   all2md.ast.visitors.NodeVisitor

Key Node Types
^^^^^^^^^^^^^^

Block-level nodes:

.. autosummary::
   :nosignatures:

   all2md.ast.nodes.Heading
   all2md.ast.nodes.Paragraph
   all2md.ast.nodes.Table
   all2md.ast.nodes.CodeBlock
   all2md.ast.nodes.List
   all2md.ast.nodes.BlockQuote

Inline nodes:

.. autosummary::
   :nosignatures:

   all2md.ast.nodes.Text
   all2md.ast.nodes.Link
   all2md.ast.nodes.Image
   all2md.ast.nodes.Code
   all2md.ast.nodes.Emphasis
   all2md.ast.nodes.Strong

AST Utilities
^^^^^^^^^^^^^

.. autosummary::
   :nosignatures:

   all2md.ast.serialization
   all2md.ast.sections
   all2md.ast.splitting
   all2md.ast.transforms
   all2md.ast.utils

Search Module
-------------

Full-text and semantic search over converted documents:

.. autosummary::
   :nosignatures:

   all2md.search.service
   all2md.search.index
   all2md.search.chunking
   all2md.search.types

Search Backends
^^^^^^^^^^^^^^^

.. autosummary::
   :nosignatures:

   all2md.search.bm25
   all2md.search.vector
   all2md.search.hybrid

Diff Module
-----------

Document comparison and diff rendering:

.. autosummary::
   :nosignatures:

   all2md.diff.text_diff
   all2md.diff.renderers

Quality Scoring
---------------

Three reads on conversion quality, answering three different questions.

:mod:`all2md.confidence` answers *"can I trust this conversion?"* It is
**reference-free**, scoring from the sanity signals the parser observed, which is
the only option for a document with no ground truth (a scanned PDF).

:mod:`all2md.roundtrip` answers *"what did this conversion lose?"* It **manufactures
a reference** by converting a document to another format and parsing it straight
back, then scores the structure that survived.

:mod:`all2md.optimize` answers *"which of these settings is best?"* — a distinct
question, and it needs a distinct objective. The confidence score cannot be used to
search: it saturates at ``100`` on anything not visibly broken, so across a sweep of
converter options it is flat and there is no gradient to climb. The round-trip score
cannot be used either, because re-parsing rendered output measures the *renderer* —
a garbled table round-trips through Markdown perfectly. So the optimizer scores the
parsed AST directly, on how much *well-formed* structure each setting recovers.

.. autosummary::
   :nosignatures:

   all2md.confidence
   all2md.roundtrip
   all2md.optimize

MCP Server
----------

Model Context Protocol server for LLM integration:

.. autosummary::
   :nosignatures:

   all2md.mcp.server
   all2md.mcp.config
   all2md.mcp.tools
   all2md.mcp.document_tools
   all2md.mcp.schemas
   all2md.mcp.security

For user-facing MCP documentation, see :doc:`/mcp`.

Packagers
---------

Submission package generators for academic publishing:

.. autosummary::
   :nosignatures:

   all2md.packagers.arxiv

Complete References
-------------------

.. toctree::
   :maxdepth: 1

   all2md.ast
   all2md.search
   all2md.diff
   all2md.confidence
   all2md.roundtrip
   all2md.optimize
   all2md.mcp
   all2md.packagers
   all2md.packagers.arxiv

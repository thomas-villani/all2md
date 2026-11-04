all2md
======

Convert documents to clean Markdown and back, and read and search them wherever you work:
in a browser, in the terminal, or through an AI assistant.

.. code-block:: bash

   pip install "all2md[pdf,docx,markdown,cli_extras]"

Those extras cover the examples below, apart from MCP, which needs its own. :doc:`formats`
lists every format and the extra it needs, and :doc:`installation` covers the other ways to
install.

What do you want to do?
-----------------------

**Turn a document into Markdown for an LLM**
   Point ``all2md`` at a file and redirect the output. See the :doc:`quickstart`, and
   :ref:`chunk-command` for splitting the result for retrieval.

   .. code-block:: bash

      all2md report.pdf > report.md

**Turn Markdown into a styled Word document**
   Use your own ``.docx`` as the source of the styles. See
   :ref:`round-trip-editing-with-template-preservation`.

   .. code-block:: bash

      all2md answer.md --out answer.docx \
        --docx-renderer-template-path house.docx --docx-renderer-clear-template-body

**Look at a document**
   Open it in a browser with the :doc:`document viewer <viewer>`, or
   :ref:`read it in the terminal <terminal-reading>`.

   .. code-block:: bash

      all2md view proposal.docx
      rcat proposal.docx

**Search PDFs and Word files for a phrase**
   Search a whole folder without converting it first. See :ref:`grep-command`.

   .. code-block:: bash

      all2md grep -i "indemnif" contracts/ -r

**Give an AI assistant your documents**
   Install the ``mcp`` extra, then point the server at a folder. :ref:`mcp-clients` shows how
   to connect your client to it. See :doc:`mcp` for everything else.

   .. code-block:: bash

      all2md-mcp --read-dirs ~/Documents

**Know how far to trust a conversion**
   Get a confidence score and the signals behind it for one document. See
   :ref:`report-command`, :doc:`pdf`, and the measured results in :doc:`benchmarks`.

   .. code-block:: bash

      all2md report scan.pdf

Using Python?
-------------

.. code-block:: python

   from all2md import to_markdown

   markdown = to_markdown("report.pdf")

Continue with the :doc:`Python workflows <python_api>` or the :doc:`API reference <api/index>`.

About this project
------------------

**all2md** is developed by Tom Villani, Ph.D. and released under the :doc:`MIT License <license>`.

* **Source code**: https://github.com/thomas-villani/all2md
* **Issues**: https://github.com/thomas-villani/all2md/issues
* **PyPI**: https://pypi.org/project/all2md/
* **Indexes**: :ref:`genindex`, :ref:`modindex`, :ref:`search`

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Get started

   installation
   quickstart
   formats

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Guides

   viewer
   mcp
   agent_skills
   batch
   attachments
   lint_guide
   github_action
   transforms
   templates
   static_sites
   recipes
   troubleshooting

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Formats

   pdf

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Reference

   cli
   options
   configuration
   environment_variables
   cheatsheet
   python_api
   api/index

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Explanation

   overview
   benchmarks
   security
   threat_model
   performance

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Extending all2md

   ast_guide
   plugins
   architecture
   integrations

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Engineering notes

   optimizations

.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: About

   license

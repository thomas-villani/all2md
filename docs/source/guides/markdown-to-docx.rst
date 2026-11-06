Markdown to a Styled Word Document
==================================

Turn Markdown, such as an answer from an LLM, into a Word document that uses your own styles.

.. code-block:: bash

   pip install "all2md[markdown,docx]"
   all2md answer.md --out answer.docx --template-docx house.docx

The ``.docx`` ending on ``--out`` is what selects Word. Without it, all2md writes Markdown and
doesn't use the template.

Convert without a template
--------------------------

.. code-block:: bash

   all2md answer.md --out answer.docx

You get real Word structure rather than manual formatting, so the Navigation pane, tables of
contents and style changes all work:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Markdown
     - Word style or feature
   * - The document's only ``#`` heading, at the start
     - ``Title``, and the headings below it move up one level
   * - Other headings
     - ``Heading 1`` to ``Heading 9``
   * - Bullet and numbered lists
     - ``List Bullet`` and ``List Number``, with ``List Bullet 2`` and so on when nested
   * - Tables
     - ``Light Grid Accent 1``
   * - Block quotes
     - ``Quote``
   * - Code blocks
     - ``CodeBlock``
   * - Inline code
     - ``Verbatim Char``
   * - Links
     - Real hyperlinks, styled ``Hyperlink``
   * - Figure captions
     - ``Caption``
   * - Footnotes
     - Real Word footnotes
   * - Math
     - Word equations

To keep every ``#`` heading as ``Heading 1`` instead of promoting the first to ``Title``, add
``--docx-renderer-no-promote-title``.

Use your house style
--------------------

Pass any ``.docx`` or Word template (``.dotx``) as the template:

.. code-block:: bash

   all2md answer.md --out answer.docx --template-docx house.docx

The output takes the template's styles, theme, page setup, headers and footers. It leaves out
the template's body text, so sample text in the template doesn't end up in your document.

``--template-docx`` is the short name for ``--docx-renderer-template-path``.

Make a template
~~~~~~~~~~~~~~~

#. Create a new document in Word.
#. Change the styles in the table above to suit your house style, along with the page margins,
   headers and footers.
#. Save it as a ``.docx`` or ``.dotx``.

**Check the styles you rely on.** The output can only use a style the template defines:

* If ``Title`` or a ``Heading`` style is missing, that text comes out as a plain paragraph. The
  Word-saved documents we tested define all of them, but a template built with another tool may
  not. Open the output and check the Navigation pane if you're unsure.
* Word only saves a table style once a document uses it. To use your own, add a table in that
  style to the template, then name it with ``--docx-renderer-table-style "Your Style"``. If the
  template has no table style, tables use a plain grid.
* List, code and hyperlink styles are created if the template doesn't have them.

A pandoc reference document also works as a template. all2md recognizes its ``Source Code``,
``Block Text`` and ``Table`` styles.

Keep the template's text
~~~~~~~~~~~~~~~~~~~~~~~~

If the template's body belongs in every document, such as a cover page or standard opening
text, keep it. Your content is added after it:

.. code-block:: bash

   all2md answer.md --out answer.docx --template-docx letterhead.docx \
     --docx-renderer-no-clear-template-body

A letterhead that sits in the page header doesn't need this, because headers and footers always
carry over.

Adjust fonts and tables
-----------------------

.. code-block:: bash

   all2md answer.md --out answer.docx \
     --docx-renderer-default-font Georgia \
     --docx-renderer-default-font-size 12 \
     --docx-renderer-code-font Consolas \
     --docx-renderer-table-style "Table Grid"

Without a template, body text defaults to Calibri 11. With one, the template's body font and
size are kept unless you set these. See :doc:`/options` for every DOCX option.

Make it the default
-------------------

To avoid typing the template each time, put it in ``.all2md.toml``. The section is named
``[docx]``:

.. code-block:: toml

   [docx]
   template_path = "house.docx"

A config file sets the template for every Word conversion, and other output formats ignore it.
See :doc:`/configuration` for where config files are found.

Use it from Python
------------------

.. code-block:: python

   from all2md import convert
   from all2md.options.docx import DocxRendererOptions

   options = DocxRendererOptions(template_path="house.docx")
   convert("answer.md", "answer.docx", renderer_options=options)

Pass ``clear_template_body=False`` to keep the template's text:

.. code-block:: python

   options = DocxRendererOptions(template_path="letterhead.docx", clear_template_body=False)

.. _round-trip-editing-with-template-preservation:

Edit an existing Word document through Markdown
-----------------------------------------------

A plain conversion to Markdown and back loses page setup, theme and custom styles. To keep them,
use the original document as the template. This suits editing with an LLM, because the LLM only
has to work with Markdown.

In a browser, ``all2md edit`` does this for you when you save a ``.docx`` back to ``.docx``:

.. code-block:: bash

   all2md edit report.docx --default-format docx

In Python, pass ``preserve_formatting=True``. all2md remembers the file the document came from
and uses it as the template:

.. code-block:: python

   from all2md import convert, from_ast, to_ast

   doc = to_ast("report.docx")

   # ... apply transforms, or have an LLM edit the document ...

   from_ast(doc, "docx", output="report.docx", preserve_formatting=True)

   # Or, for a direct pass through the document tree:
   convert("input.docx", "output.docx", preserve_formatting=True)

This needs a file path, because that's how all2md finds the original. If you parsed from a stream,
or want a different document as the template, set ``template_path`` as shown in
`Use it from Python`_.

What carries over and what doesn't
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Paragraph styles carry over if the template defines them, so a paragraph in a ``Chapter Title``
style stays in that style rather than becoming ``Heading 1``.

These are lost:

* Run-level character styles, such as ``Quote Char``
* Direct formatting applied outside named styles
* Content controls
* Drawings and SmartArt
* Comments anchored to a run

Other output formats
--------------------

PowerPoint and OpenDocument Text have template options too, ``--pptx-renderer-template-path``
and ``--odt-renderer-template-path``. They work differently from Word: the template's slides or
text stay, and your content is added after them.

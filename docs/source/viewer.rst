Document Viewer
===============

``all2md view`` shows converted documents in a browser instead of piping Markdown to a
file:

* Given a document, it converts it to a self-contained HTML page and opens it in your
  browser (or a standalone window with ``-w``).
* Given a folder or a glob pattern, it starts a local server and opens a listing of the
  documents, each converted when you open it.

To read a document in the terminal instead, see ``rcat`` and ``all2md read`` in
:doc:`cli`.

Both share the theming, diagram rendering, and syntax-highlighting features described
below. For the exhaustive list of flags, see the ``view`` section of the :doc:`cli`
reference.

.. note::

   ``all2md serve`` is deprecated: ``all2md view`` on a folder or a glob does what it did.
   ``serve`` still works in 1.18, printing a note, and will be removed in the next
   release. Its upload form and ``/api/convert`` endpoint were removed in 1.18; convert
   from a program with the Python API or ``all2md mcp`` instead.

Quick start
-----------

.. code-block:: bash

   # View a single file
   all2md view report.pdf
   all2md view notes.md --dark

   # Browse a whole folder (a listing of every document; click one to read it)
   all2md view ./docs
   all2md view ./docs --recursive
   all2md view "reports/*.pdf"

``view`` accepts ``-`` for stdin, so you can preview piped content:

.. code-block:: bash

   echo "# Hello" | all2md view -

Diagrams and syntax highlighting
--------------------------------

When viewing or serving, all2md automatically enriches the page:

* **Mermaid diagrams** – fenced code blocks tagged ``mermaid`` are rendered as diagrams
  using `mermaid.js <https://mermaid.js.org/>`_.
* **Syntax highlighting** – code blocks (and raw source files such as ``.py`` or ``.js``)
  are highlighted with `highlight.js <https://highlightjs.org/>`_, matching each block's
  language.

Both libraries are loaded from ``cdn.jsdelivr.net``. This is on by default; disable either
with ``--no-mermaid`` / ``--no-syntax-highlight``. Offline, the page still renders --
diagrams appear as their source text and code is shown without highlighting. The dark
variants are selected automatically with ``--dark`` or the ``dark`` theme.

For example, a Markdown file containing:

.. code-block:: text

   ```mermaid
   graph TD
       A[Start] --> B{Ready?}
       B -- Yes --> C[View it]
       B -- No --> A
   ```

renders as a flowchart in ``all2md view``.

Themes
------

Every page is built from a **theme**: a small HTML template with ``{TITLE}`` and
``{CONTENT}`` placeholders (plus optional ``{TOC}``, ``{AUTHOR}``, ``{DATE}``,
``{DESCRIPTION}``). Select one with ``--theme`` on either command.

Built-in themes
~~~~~~~~~~~~~~~

* ``minimal`` (default) – clean, centered layout
* ``dark`` – dark mode (also reachable via ``--dark``)
* ``newspaper`` – serif, justified, drop-cap first paragraph
* ``docs`` – GitHub-style technical documentation
* ``sidebar`` – two-column layout with a sticky TOC (use with ``--toc``)

.. code-block:: bash

   all2md view article.md --theme newspaper
   all2md view ./docs --theme docs

.. _viewer-custom-theme:

Writing a custom theme
~~~~~~~~~~~~~~~~~~~~~~~

A theme is just an HTML file. Save the following as ``my-theme.html`` -- the only
requirement is a ``{CONTENT}`` placeholder where the converted document is injected:

.. code-block:: html

   <!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{TITLE}</title>
       <style>
           body {
               font-family: "Iowan Old Style", Georgia, serif;
               max-width: 46rem;
               margin: 3rem auto;
               padding: 0 1.25rem;
               color: #2b2b2b;
               line-height: 1.7;
           }
           h1, h2, h3 { font-family: "Helvetica Neue", Arial, sans-serif; }
           h1 { border-bottom: 3px double #ccc; padding-bottom: .3rem; }
           a { color: #8a1f11; }
           pre {
               background: #faf7f0;
               border: 1px solid #e7e0d0;
               border-radius: 6px;
               padding: 1rem;
               overflow-x: auto;
           }
           blockquote {
               border-left: 4px solid #d9c9a3;
               margin: 1.5rem 0;
               padding-left: 1rem;
               color: #555;
           }
       </style>
   </head>
   <body>
       {CONTENT}
   </body>
   </html>

Then point ``--theme`` at the file:

.. code-block:: bash

   all2md view document.pdf --theme ./my-theme.html
   all2md view ./docs --theme ./my-theme.html

Because mermaid.js and highlight.js are injected automatically, your theme does **not**
need to include any diagram or highlighting scripts -- just style ``pre``/``code`` to taste.

CSS-only themes
~~~~~~~~~~~~~~~

If you only want to change styling, skip the HTML boilerplate and point ``--theme`` at a
plain ``.css`` file. all2md wraps it in a minimal HTML shell automatically:

.. code-block:: css

   /* brand.css */
   body { font-family: system-ui, sans-serif; max-width: 50rem; margin: 2rem auto; }
   h1, h2, h3 { color: #0b5; }
   a { color: #0b5; }

.. code-block:: bash

   all2md view report.pdf --theme ./brand.css
   all2md view ./docs --theme ./brand.css

Named themes in configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register reusable theme names in a ``[themes]`` table in any all2md configuration file
(``.all2md.toml``, ``pyproject.toml`` under ``[tool.all2md.themes]``, ...). Values can be
``.html`` templates or ``.css`` files, and paths may use ``~``:

.. code-block:: toml

   [themes]
   corporate = "~/themes/corporate.html"
   brand = "~/themes/brand.css"

   # Optionally set a default theme for the command
   [view]
   theme = "corporate"

Now the registered names resolve on the command line:

.. code-block:: bash

   all2md view report.pdf --theme corporate
   all2md view ./docs --theme brand

See :doc:`configuration` for how configuration files are discovered and merged.

Browsing a folder
-----------------

Point ``all2md view`` at a folder, or at a quoted glob pattern, to get a browsable
listing. The listing:

* lists only files all2md can convert (unsupported files are hidden);
* offers an aligned **table** view (Name / Size / Modified / Created) and a **card** view,
  with a toggle that is remembered per browser (table is the default);
* updates live as files are added or removed (see ``--poll-interval``);
* is generated even when the folder has a README, which rarely lists everything; pass
  ``--index-page`` to show a hand-authored ``index.html`` / ``index.md`` / ``README.md``
  instead.

Images a document names by path are shown when they are inside the folder being viewed;
the server never reads files outside it. It listens on ``127.0.0.1`` only, unless you
pass ``--host``.

.. code-block:: bash

   # Browse a docs tree, subfolders included
   all2md view ./docs --recursive

   # Show the repo README in place of the generated listing
   all2md view . --recursive --index-page

See also
--------

* :doc:`cli` -- complete flag reference for ``view``
* :doc:`configuration` -- configuration files, ``[themes]``, and per-command defaults
* :doc:`static_sites` -- generating a static HTML site instead of serving live

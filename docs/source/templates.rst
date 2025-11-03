Custom Templates with Jinja2
=============================

all2md includes a powerful Jinja2-based template renderer that allows you to create custom output formats without writing any Python code. Simply write a Jinja2 template and all2md will handle the rest.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

The Jinja2 renderer provides a flexible way to transform documents into any text-based format. Whether you need XML, YAML, custom markup, or even terminal output with ANSI codes, you can achieve it by writing a template.

**Key capabilities:**

- Full access to the document AST (Abstract Syntax Tree)
- Pre-computed collections (headings, links, images, footnotes)
- Node rendering filters for recursive rendering
- Format-specific escape filters (XML, HTML, LaTeX, YAML, Markdown)
- AST traversal helper functions
- Custom context injection
- Configurable escaping strategies

Quick Start
-----------

**1. Create a template file** (e.g., ``outline.txt.jinja2``):

.. code-block:: jinja

   # {{ metadata.title or "Document" }}

   {% for h in headings -%}
   {{ "  " * (h.level - 1) }}{{ loop.index }}. {{ h.text }}
   {% endfor %}

**2. Use it from Python:**

.. code-block:: python

   from all2md import convert
   from all2md.options import JinjaRendererOptions

   options = JinjaRendererOptions(
       template_file="outline.txt.jinja2"
   )

   convert("document.pdf", "outline.txt",
           target_format="jinja",
           renderer_options=options)

**3. Or from the CLI:**

.. code-block:: bash

   all2md document.pdf --format jinja \
       --jinja-template-file outline.txt.jinja2 \
       --out outline.txt

Template Context Reference
--------------------------

Every template receives a rich context with access to the document structure, metadata, and helper utilities.

Core Variables
~~~~~~~~~~~~~~

``document``
   The root AST node (``Document`` object). Contains the full document tree with a ``children`` list.

``ast``
   Dictionary representation of the entire AST. Useful for debugging or simple property access.

``metadata``
   Document metadata object with attributes:

   - ``title`` (str or None) - Document title
   - ``author`` (str or None) - Document author
   - ``date`` (str or None) - Document date
   - ``description`` (str or None) - Document description
   - ``keywords`` (list[str]) - Document keywords
   - ``language`` (str or None) - Document language

``title``
   Quick access to ``metadata.title`` (commonly used).

Pre-computed Collections
~~~~~~~~~~~~~~~~~~~~~~~~~

These collections are only available if ``enable_traversal_helpers=True`` (default is ``False`` for performance).

``headings``
   List of all heading nodes in the document. Each heading has:

   - ``level`` (int) - Heading level (1-6)
   - ``content`` (list) - List of inline nodes (Text, Emphasis, etc.)
   - ``text`` (str) - Plain text content (extracted automatically)
   - ``node_id`` (str or None) - Optional heading ID

   Example:

   .. code-block:: jinja

      {% for h in headings %}
      {{ "  " * (h.level - 1) }}{{ h.text }}
      {% endfor %}

``links``
   List of all link nodes. Each link has:

   - ``url`` (str) - Link destination
   - ``title`` (str or None) - Optional link title
   - ``content`` (list) - Link text as inline nodes
   - ``text`` (str) - Plain text of link content

   Example:

   .. code-block:: jinja

      Links in this document:
      {% for link in links %}
      - {{ link.text }}: {{ link.url }}
      {% endfor %}

``images``
   List of all image nodes. Each image has:

   - ``url`` (str) - Image source URL or path
   - ``alt_text`` (str or None) - Alternative text
   - ``title`` (str or None) - Optional image title

   Example:

   .. code-block:: jinja

      Images: {{ images|length }}
      {% for img in images %}
      - {{ img.alt_text or "Untitled" }}
      {% endfor %}

``footnotes``
   List of all footnote reference nodes. Each footnote has:

   - ``label`` (str) - Footnote label/identifier
   - ``content`` (list) - Footnote content as block nodes

   Example:

   .. code-block:: jinja

      Footnotes:
      {% for fn in footnotes %}
      [{{ fn.label }}]: {{ fn.content|map('render')|join('') }}
      {% endfor %}

Filter Reference
----------------

Node Rendering Filters
~~~~~~~~~~~~~~~~~~~~~~~

These filters are only available if ``enable_render_filter=True`` (default is ``False``).

``render``
   Recursively renders a node or list of nodes to the target format.

   **Parameters:**

   - ``format`` (str, optional) - Target format (default from options)

   **Example:**

   .. code-block:: jinja

      {# Render a node to Markdown #}
      {{ node|render }}

      {# Render to a specific format #}
      {{ node|render('html') }}

      {# Render a list of inline nodes #}
      {{ heading.content|map('render')|join('') }}

``render_inline``
   Renders inline content (list of inline nodes) to plain text.

   **Example:**

   .. code-block:: jinja

      {{ paragraph.content|render_inline }}

Escape Filters
~~~~~~~~~~~~~~

These filters are only available if ``enable_escape_filters=True`` (default is ``False``).

``escape_xml``
   Escapes text for XML output (``&``, ``<``, ``>``, ``"``, ``'``).

   .. code-block:: jinja

      <title>{{ metadata.title|escape_xml }}</title>

``escape_html``
   Escapes text for HTML output (``&``, ``<``, ``>``, ``"``, ``'``).

   .. code-block:: jinja

      <h1>{{ heading.text|escape_html }}</h1>

``escape_latex``
   Escapes text for LaTeX output (``&``, ``%``, ``$``, ``#``, ``_``, ``{``, ``}``, ``~``, ``^``, ``\``).

   .. code-block:: jinja

      \section{{{ heading.text|escape_latex }}}

``escape_yaml``
   Escapes text for YAML output (handles special characters and multiline strings).

   .. code-block:: jinja

      title: {{ metadata.title|escape_yaml }}

``escape_markdown``
   Escapes text for Markdown output (``*``, ``_``, ``[``, ``]``, ``(``, ``)``, etc.).

   .. code-block:: jinja

      # {{ heading.text|escape_markdown }}

Function Reference
------------------

Helper Functions
~~~~~~~~~~~~~~~~

These functions are only available if ``enable_traversal_helpers=True`` (default is ``False``).

``find_nodes_by_type(node_type)``
   Finds all nodes of a specific type in the document.

   **Parameters:**

   - ``node_type`` (str) - Node type name (e.g., "Heading", "Link", "Image")

   **Returns:** List of matching nodes

   **Example:**

   .. code-block:: jinja

      {# Find all code blocks #}
      {% set code_blocks = find_nodes_by_type("CodeBlock") %}
      Code blocks: {{ code_blocks|length }}

``node_type``
   Test filter that returns the type name of a node.

   **Example:**

   .. code-block:: jinja

      {% if node|node_type == "Heading" %}
      # {{ node.content|map('render')|join('') }}
      {% endif %}

Template Creation Walkthrough
------------------------------

Let's walk through creating a custom DocBook XML template.

**Step 1: Plan the structure**

DocBook uses specific XML tags like ``<article>``, ``<section>``, ``<para>``, etc. We need to map AST nodes to these tags.

**Step 2: Create the template file** (``docbook.xml.jinja2``):

.. code-block:: jinja

   <?xml version="1.0" encoding="UTF-8"?>
   <article xmlns="http://docbook.org/ns/docbook" version="5.0">
     <info>
       <title>{{ metadata.title|escape_xml or "Untitled Document" }}</title>
       {% if metadata.author -%}
       <author><personname>{{ metadata.author|escape_xml }}</personname></author>
       {% endif -%}
       {% if metadata.date -%}
       <date>{{ metadata.date|escape_xml }}</date>
       {% endif -%}
     </info>

     {% for node in document.children -%}
     {%- if node|node_type == "Heading" -%}
     <section>
       <title>{{ node.content|map('render')|join('')|escape_xml }}</title>
     </section>
     {%- elif node|node_type == "Paragraph" -%}
     <para>{{ node.content|map('render')|join('')|escape_xml }}</para>
     {%- elif node|node_type == "CodeBlock" -%}
     <programlisting{% if node.language %} language="{{ node.language }}"{% endif %}>{{ node.content|escape_xml }}</programlisting>
     {%- endif -%}
     {% endfor -%}
   </article>

**Step 3: Configure the renderer**

.. code-block:: python

   from all2md import convert
   from all2md.options import JinjaRendererOptions

   options = JinjaRendererOptions(
       template_file="docbook.xml.jinja2",
       escape_strategy="xml",           # Auto-escape for XML
       enable_render_filter=True,       # Enable node rendering
       enable_escape_filters=True,      # Enable escape filters
       enable_traversal_helpers=True    # Enable find functions
   )

   convert("document.pdf", "output.xml",
           target_format="jinja",
           renderer_options=options)

**Step 4: Test and refine**

Run the conversion and check the output. Adjust the template as needed for edge cases, proper indentation, and complete coverage of node types.

Example Templates Gallery
--------------------------

all2md includes several example templates in the ``examples/jinja-templates/`` directory:

DocBook XML
~~~~~~~~~~~

**File:** ``docbook.xml.jinja2``

Produces valid DocBook 5.0 XML suitable for technical documentation systems.

**Features:**

- Full XML escaping
- Metadata mapping to DocBook ``<info>`` element
- Section hierarchy
- Code blocks with language attributes

**Use case:** Technical documentation, book authoring, documentation toolchains

YAML Metadata
~~~~~~~~~~~~~

**File:** ``metadata.yaml.jinja2``

Extracts document structure and metadata to YAML format.

**Features:**

- Document statistics (heading count, link count, image count)
- Table of contents with heading hierarchy
- Link and image inventories

**Use case:** Document analysis, metadata extraction, content auditing

ANSI Terminal
~~~~~~~~~~~~~

**File:** ``ansi-terminal.txt.jinja2``

Creates colorful, formatted terminal output with Unicode box drawing characters.

**Features:**

- ANSI color codes for syntax highlighting
- Unicode box characters for borders and structure
- Styled headings (█ level 1, ▓ level 2, ▒ level 3)
- Code blocks in bordered frames
- Document statistics footer

**Use case:** Terminal documentation viewers, CLI help systems, README rendering

Custom Outline
~~~~~~~~~~~~~~

**File:** ``custom-outline.txt.jinja2``

Generates a human-readable document outline.

**Features:**

- Hierarchical heading list with indentation
- Document statistics summary
- Plain text format

**Use case:** Document navigation, quick previews, outline generation

Best Practices
--------------

Performance Optimization
~~~~~~~~~~~~~~~~~~~~~~~~

1. **Disable unused features:** Set ``enable_render_filter=False``, ``enable_escape_filters=False``, and ``enable_traversal_helpers=False`` if you don't need them.

2. **Use pre-computed collections:** Access ``headings``, ``links``, ``images``, and ``footnotes`` instead of calling ``find_nodes_by_type()`` repeatedly.

3. **Cache expensive operations:** Use Jinja2's ``{% set %}`` to cache computed values.

   .. code-block:: jinja

      {% set total_links = links|length %}
      {% set total_images = images|length %}

Escaping and Security
~~~~~~~~~~~~~~~~~~~~~

1. **Always escape user content:** Use appropriate escape filters for your output format.

   .. code-block:: jinja

      {# Good - escaped #}
      <title>{{ metadata.title|escape_xml }}</title>

      {# Bad - unescaped #}
      <title>{{ metadata.title }}</title>

2. **Use escape_strategy:** Set a default escape strategy in options to avoid forgetting.

   .. code-block:: python

      JinjaRendererOptions(
          template_file="template.xml.jinja2",
          escape_strategy="xml"
      )

3. **Mark safe content carefully:** Only use ``|safe`` when you're absolutely certain the content is safe.

Template Organization
~~~~~~~~~~~~~~~~~~~~~

1. **Break complex templates into macros:**

   .. code-block:: jinja

      {% macro render_heading(heading) -%}
      <h{{ heading.level }}>{{ heading.content|map('render')|join('') }}</h{{ heading.level }}>
      {%- endmacro %}

      {% for node in document.children %}
        {%- if node|node_type == "Heading" -%}
          {{ render_heading(node) }}
        {%- endif -%}
      {% endfor %}

2. **Use template inheritance:** Create a base template with common structure.

   .. code-block:: jinja

      {# base.xml.jinja2 #}
      <?xml version="1.0"?>
      <document>
        {% block content %}{% endblock %}
      </document>

      {# custom.xml.jinja2 #}
      {% extends "base.xml.jinja2" %}
      {% block content %}
        {{ document.children|map('render')|join('') }}
      {% endblock %}

3. **Add comments:** Document complex logic and template sections.

   .. code-block:: jinja

      {# Table of Contents Section #}
      {% if headings and headings|length > 0 %}
      <nav>
        {# Render headings hierarchically #}
        {% for h in headings %}
          <a href="#{{ h.node_id }}">{{ h.text }}</a>
        {% endfor %}
      </nav>
      {% endif %}

Error Handling
~~~~~~~~~~~~~~

1. **Check for None values:**

   .. code-block:: jinja

      {% if metadata.title %}
        <title>{{ metadata.title }}</title>
      {% else %}
        <title>Untitled</title>
      {% endif %}

2. **Use default filter:**

   .. code-block:: jinja

      <title>{{ metadata.title|default("Untitled") }}</title>

3. **Enable strict_undefined for development:**

   .. code-block:: python

      JinjaRendererOptions(
          template_file="template.jinja2",
          strict_undefined=True  # Raises error on undefined variables
      )

Advanced Techniques
-------------------

Inline Template Strings
~~~~~~~~~~~~~~~~~~~~~~~

For simple templates, use ``template_string`` instead of ``template_file``:

.. code-block:: python

   from all2md import convert
   from all2md.options import JinjaRendererOptions

   template = """
   # {{ metadata.title or "Document" }}

   {% for h in headings %}
   {{ "  " * (h.level - 1) }}- {{ h.text }}
   {% endfor %}
   """

   options = JinjaRendererOptions(
       template_string=template,
       enable_traversal_helpers=True
   )

   convert("doc.pdf", "outline.txt",
           target_format="jinja",
           renderer_options=options)

Custom Escape Functions
~~~~~~~~~~~~~~~~~~~~~~~

Provide your own escape function for specialized formats:

.. code-block:: python

   def escape_csv(text: str) -> str:
       """Escape text for CSV format."""
       if '"' in text or ',' in text or '\n' in text:
           return '"' + text.replace('"', '""') + '"'
       return text

   options = JinjaRendererOptions(
       template_file="export.csv.jinja2",
       escape_strategy="custom",
       custom_escape_function=escape_csv
   )

Extra Context Variables
~~~~~~~~~~~~~~~~~~~~~~~

Inject additional context variables into templates:

.. code-block:: python

   options = JinjaRendererOptions(
       template_file="report.html.jinja2",
       extra_context={
           "company_name": "Acme Corp",
           "report_date": "2025-01-24",
           "logo_url": "https://example.com/logo.png"
       }
   )

Then use in template:

.. code-block:: jinja

   <header>
     <img src="{{ logo_url }}" alt="{{ company_name }}">
     <span>Report Date: {{ report_date }}</span>
   </header>

CLI Integration
---------------

All template options are available from the command line:

.. code-block:: bash

   # Basic usage
   all2md doc.pdf --format jinja --jinja-template-file template.xml.jinja2

   # With escape strategy
   all2md doc.pdf --format jinja \
       --jinja-template-file template.xml.jinja2 \
       --jinja-escape-strategy xml

   # Enable all features
   all2md doc.pdf --format jinja \
       --jinja-template-file template.jinja2 \
       --jinja-enable-render-filter \
       --jinja-enable-escape-filters \
       --jinja-enable-traversal-helpers

   # With inline template string
   all2md doc.pdf --format jinja \
       --jinja-template-string "# {{ title }}"

See Also
--------

- :doc:`python_api` - Overview of bidirectional conversion including templates
- :doc:`recipes` - Step-by-step template creation tutorial
- :doc:`ast_guide` - Understanding the AST structure for template authoring
- ``examples/jinja-templates/`` - Gallery of example templates
- ``examples/jinja_template_demo.py`` - Python API examples

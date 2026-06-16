# Jinja2 Template Examples for all2md

This directory contains example Jinja2 templates demonstrating the generic template renderer in all2md.

## Available Templates

### 1. `docbook.xml.jinja2` - DocBook XML

Converts documents to DocBook XML format, suitable for technical documentation.

**Usage:**
```python
from all2md import Document
from all2md.renderers.jinja import JinjaRenderer
from all2md.options.jinja import JinjaRendererOptions

options = JinjaRendererOptions(
    template_file="examples/jinja-templates/docbook.xml.jinja2",
    escape_strategy="xml",
    enable_escape_filters=True,
    enable_traversal_helpers=True
)

renderer = JinjaRenderer(options)
output = renderer.render_to_string(document)
```

### 2. `metadata.yaml.jinja2` - YAML Metadata

Extracts document structure and metadata as YAML.

**Usage:**
```python
options = JinjaRendererOptions(
    template_file="examples/jinja-templates/metadata.yaml.jinja2",
    escape_strategy="yaml",
    enable_escape_filters=True,
    enable_traversal_helpers=True
)

renderer = JinjaRenderer(options)
output = renderer.render_to_string(document)
```

### 3. `custom-outline.txt.jinja2` - Custom Text Outline

Generates a human-readable document outline with table of contents.

**Usage:**
```python
options = JinjaRendererOptions(
    template_file="examples/jinja-templates/custom-outline.txt.jinja2",
    enable_traversal_helpers=True
)

renderer = JinjaRenderer(options)
output = renderer.render_to_string(document)
```

## Template Features

All templates have access to:

### Context Variables
- `document` - The Document node (Node object)
- `ast` - The document as a dictionary
- `metadata` - Document metadata dictionary
- `title` - Document title (shorthand for metadata.title)
- `headings` - List of all heading nodes (if enabled)
- `links` - List of all link nodes (if enabled)
- `images` - List of all image nodes (if enabled)
- `footnotes` - List of all footnote definitions (if enabled)

### Filters
- `render` - Render a node with default logic
- `render_inline` - Render inline content
- `to_dict` - Convert Node to dictionary
- `escape_xml`, `escape_html` - XML/HTML escaping
- `escape_latex` - LaTeX escaping
- `escape_yaml` - YAML escaping
- `escape_markdown` - Markdown escaping
- `node_type` - Get node type name

### Functions
- `get_headings(doc)` - Extract all heading nodes
- `get_links(doc)` - Extract all link nodes
- `get_images(doc)` - Extract all image nodes
- `get_footnotes(doc)` - Extract all footnote definitions
- `find_nodes(doc, node_type)` - Find all nodes of specified type

## Creating Custom Templates

Create your own templates by:

1. Define the output format structure
2. Use `{% for node in document.children %}` to iterate over content
3. Use `{% if node|node_type == "Heading" %}` to handle specific node types
4. Apply appropriate escape filters for your format
5. Use traversal helpers for document analysis

Example template snippet:
```jinja2
{% for node in document.children %}
  {% if node|node_type == "Heading" %}
    <h{{ node.level }}>{{ node.content|map('render')|join('')|escape_html }}</h{{ node.level }}>
  {% elif node|node_type == "Paragraph" %}
    <p>{{ node.content|map('render')|join('')|escape_html }}</p>
  {% endif %}
{% endfor %}
```

## See Also

- [all2md Documentation](../../docs/)
- [JinjaRenderer API](../../docs/source/api/all2md.renderers.jinja.rst)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)

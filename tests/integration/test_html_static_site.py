#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for HTML static site generation.

Tests demonstrate complete workflows for generating static sites
from documents using templates.

"""


import pytest

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    Paragraph,
    Text,
)
from all2md.options import HtmlRendererOptions
from all2md.renderers.html import HtmlRenderer


@pytest.mark.integration
class TestStaticSiteGeneration:
    """Integration tests for static site generation workflows."""

    def test_blog_post_with_jinja_template(self, tmp_path):
        """Test generating a blog post with Jinja template."""
        pytest.importorskip("jinja2")

        # Create a blog post template
        template = tmp_path / "blog_post.html"
        template.write_text("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <meta name="author" content="{{ metadata.author }}">
    <meta name="description" content="{{ metadata.description }}">
    <style>
        body { max-width: 800px; margin: 0 auto; padding: 2rem; font-family: sans-serif; }
        .meta { color: #666; font-size: 0.9em; }
        h1 { border-bottom: 2px solid #333; }
    </style>
</head>
<body>
    <article>
        <header>
            <h1>{{ title }}</h1>
            <div class="meta">
                By {{ metadata.author }} | {{ metadata.date }}
            </div>
        </header>
        <div class="content">
            {{ content }}
        </div>
        {% if headings %}
        <aside>
            <h2>Table of Contents</h2>
            {{ toc_html }}
        </aside>
        {% endif %}
    </article>
</body>
</html>""", encoding='utf-8')

        # Create blog post document
        doc = Document(
            metadata={
                'title': 'Understanding HTML Templates',
                'author': 'Jane Doe',
                'date': '2025-01-15',
                'description': 'A guide to HTML templating in all2md'
            },
            children=[
                Heading(level=2, content=[Text(content="Introduction")]),
                Paragraph(content=[Text(content="Templates make it easy to create consistent HTML output.")]),
                Heading(level=2, content=[Text(content="How It Works")]),
                Paragraph(content=[Text(content="The renderer supports three template modes.")]),
                CodeBlock(
                    content='renderer = HtmlRenderer(HtmlRendererOptions(template_mode="jinja"))',
                    language='python'
                ),
            ]
        )

        # Render with Jinja template
        options = HtmlRendererOptions(
            template_mode='jinja',
            template_file=str(template),
            syntax_highlighting=True
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Verify output
        assert '<!DOCTYPE html>' in result
        assert '<title>Understanding HTML Templates</title>' in result
        assert 'By Jane Doe | 2025-01-15' in result
        assert '<h2 id="heading-0">Introduction</h2>' in result
        assert 'language-python' in result
        assert 'Table of Contents' in result

    def test_documentation_site_with_injection(self, tmp_path):
        """Test injecting documentation into existing site layout."""
        # Create a site layout template
        layout = tmp_path / "layout.html"
        layout.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>Documentation</title>
    <link rel="stylesheet" href="/styles.css">
</head>
<body>
    <nav class="sidebar">
        <ul>
            <li><a href="/">Home</a></li>
            <li><a href="/docs">Docs</a></li>
        </ul>
    </nav>
    <main id="content">
        <!-- Content will be injected here -->
    </main>
    <footer>
        <p>&copy; 2025 My Project</p>
    </footer>
</body>
</html>""", encoding='utf-8')

        # Create documentation content
        doc = Document(children=[
            Heading(level=1, content=[Text(content="API Reference")]),
            Heading(level=2, content=[Text(content="Classes")]),
            Paragraph(content=[Text(content="The main classes in this library.")]),
            Heading(level=2, content=[Text(content="Functions")]),
            Paragraph(content=[Text(content="Helper functions for common tasks.")]),
        ])

        # Inject into layout
        options = HtmlRendererOptions(
            template_mode='inject',
            template_file=str(layout),
            template_selector='#content',
            injection_mode='replace'
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Verify structure is preserved
        assert '<nav class="sidebar">' in result
        assert '<footer>' in result
        assert '<main id="content">' in result

        # Verify content is injected
        assert '<h1 id="heading-0">API Reference</h1>' in result
        assert '<h2 id="heading-1">Classes</h2>' in result

    def test_article_with_custom_styling(self, tmp_path):
        """Test generating article with custom CSS classes."""
        # Simple template
        template = tmp_path / "article.html"
        template.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>{TITLE}</title>
    <style>
        .prose-heading { color: #1a1a1a; font-weight: 700; margin-top: 2rem; }
        .prose-para { line-height: 1.6; margin-bottom: 1rem; }
        .quote-block { border-left: 4px solid #e0e0e0; padding-left: 1rem; font-style: italic; }
        .code-snippet { background: #f5f5f5; border-radius: 4px; }
    </style>
</head>
<body>
{CONTENT}
</body>
</html>""", encoding='utf-8')

        # Create document
        doc = Document(
            metadata={'title': 'Styled Article'},
            children=[
                Heading(level=1, content=[Text(content="Main Title")]),
                Paragraph(content=[Text(content="This is a paragraph with custom styling.")]),
                BlockQuote(children=[
                    Paragraph(content=[Text(content="A quoted passage.")])
                ]),
                CodeBlock(content="code example", language="javascript"),
            ]
        )

        # Render with custom CSS classes
        options = HtmlRendererOptions(
            template_mode='replace',
            template_file=str(template),
            css_class_map={
                'Heading': 'prose-heading',
                'Paragraph': 'prose-para',
                'BlockQuote': 'quote-block',
                'CodeBlock': 'code-snippet',
            },
            syntax_highlighting=True
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Verify custom classes are applied
        assert 'class="prose-heading"' in result
        assert 'class="prose-para"' in result
        assert 'class="quote-block"' in result
        assert 'language-javascript code-snippet' in result

    def test_multi_document_workflow(self, tmp_path):
        """Test generating multiple pages with shared template."""
        # Shared template
        template = tmp_path / "page.html"
        template.write_text("""<!DOCTYPE html>
<html>
<head><title>{TITLE}</title></head>
<body>
    <header><h1>{TITLE}</h1></header>
    <div class="content">{CONTENT}</div>
    <footer><p>Part of the documentation</p></footer>
</body>
</html>""", encoding='utf-8')

        # Create multiple documents
        docs = [
            Document(
                metadata={'title': 'Getting Started'},
                children=[Paragraph(content=[Text(content="Welcome to the guide.")])]
            ),
            Document(
                metadata={'title': 'Configuration'},
                children=[Paragraph(content=[Text(content="How to configure.")])]
            ),
            Document(
                metadata={'title': 'API Reference'},
                children=[Paragraph(content=[Text(content="API documentation.")])]
            ),
        ]

        # Render all pages
        options = HtmlRendererOptions(
            template_mode='replace',
            template_file=str(template)
        )
        renderer = HtmlRenderer(options)

        outputs = []
        for doc in docs:
            result = renderer.render_to_string(doc)
            outputs.append(result)

        # Verify all pages share structure
        for output in outputs:
            assert '<header>' in output
            assert '<footer>' in output
            assert 'Part of the documentation' in output

        # Verify each has unique content
        assert 'Getting Started' in outputs[0]
        assert 'Configuration' in outputs[1]
        assert 'API Reference' in outputs[2]

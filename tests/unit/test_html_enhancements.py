"""Tests for HTML parser enhancements (figure, details, code detection, microdata)."""

from all2md.parsers.html import HtmlToAstConverter
from all2md.options import HtmlOptions
from all2md.ast.nodes import BlockQuote, Paragraph, Image, Strong, Emphasis, CodeBlock


def test_figure_blockquote_rendering():
    """Test figure element rendered as blockquote."""
    html = """
    <figure>
        <img src="image.jpg" alt="Test image">
        <figcaption>This is a caption</figcaption>
    </figure>
    """

    options = HtmlOptions(figure_rendering="blockquote")
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    # Should create a blockquote with image and caption
    assert len(doc.children) > 0
    blockquote = doc.children[0]
    assert isinstance(blockquote, BlockQuote)

    # Check for image and caption in children
    has_image = any(
        isinstance(child, Paragraph) and any(isinstance(node, Image) for node in child.content)
        for child in blockquote.children
    )
    has_caption = any(
        isinstance(child, Paragraph) and any(isinstance(node, Emphasis) for node in child.content)
        for child in blockquote.children
    )

    assert has_image, "Blockquote should contain image"
    assert has_caption, "Blockquote should contain caption"


def test_figure_image_with_caption_rendering():
    """Test figure element rendered as image with caption."""
    html = """
    <figure>
        <img src="photo.png">
        <figcaption>A beautiful photo</figcaption>
    </figure>
    """

    options = HtmlOptions(figure_rendering="image_with_caption")
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    # Should create a paragraph with an image
    assert len(doc.children) > 0
    para = doc.children[0]
    assert isinstance(para, Paragraph)

    # Check for image with caption as alt text (when no alt text exists)
    image = para.content[0]
    assert isinstance(image, Image)
    assert image.alt_text == "A beautiful photo"


def test_details_blockquote_rendering():
    """Test details/summary rendered as blockquote."""
    html = """
    <details>
        <summary>Click to expand</summary>
        <p>Hidden content here</p>
    </details>
    """

    options = HtmlOptions(details_rendering="blockquote")
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    # Should create a blockquote
    assert len(doc.children) > 0
    blockquote = doc.children[0]
    assert isinstance(blockquote, BlockQuote)

    # First child should have the summary as strong text
    first_para = blockquote.children[0]
    assert isinstance(first_para, Paragraph)
    assert any(isinstance(node, Strong) for node in first_para.content)


def test_details_ignore_rendering():
    """Test details element can be ignored."""
    html = """
    <details>
        <summary>Ignored</summary>
        <p>This should not appear</p>
    </details>
    <p>But this should</p>
    """

    options = HtmlOptions(details_rendering="ignore")
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    # Should only have the paragraph outside details
    assert len(doc.children) == 1
    para = doc.children[0]
    assert isinstance(para, Paragraph)


def test_code_language_prism_detection():
    """Test code language detection for Prism.js syntax."""
    html = '<pre><code class="language-python">print("hello")</code></pre>'

    converter = HtmlToAstConverter()
    doc = converter.parse(html)

    code_block = doc.children[0]
    assert isinstance(code_block, CodeBlock)
    assert code_block.language == "python"


def test_code_language_highlightjs_detection():
    """Test code language detection for Highlight.js syntax."""
    html = '<pre><code class="hljs-javascript">console.log("test")</code></pre>'

    converter = HtmlToAstConverter()
    doc = converter.parse(html)

    code_block = doc.children[0]
    assert isinstance(code_block, CodeBlock)
    assert code_block.language == "javascript"


def test_code_language_alias_expansion():
    """Test that language aliases are expanded."""
    test_cases = [
        ('<pre><code class="language-js">code</code></pre>', "javascript"),
        ('<pre><code class="language-py">code</code></pre>', "python"),
        ('<pre><code class="language-ts">code</code></pre>', "typescript"),
        ('<pre><code class="language-sh">code</code></pre>', "bash"),
    ]

    for html, expected_lang in test_cases:
        converter = HtmlToAstConverter()
        doc = converter.parse(html)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == expected_lang, f"Expected {expected_lang}, got {code_block.language}"


def test_code_language_data_attribute():
    """Test code language from data-lang attribute."""
    html = '<pre data-lang="rust"><code>fn main() {}</code></pre>'

    converter = HtmlToAstConverter()
    doc = converter.parse(html)

    code_block = doc.children[0]
    assert isinstance(code_block, CodeBlock)
    assert code_block.language == "rust"


def test_microdata_extraction_opengraph():
    """Test extraction of Open Graph metadata."""
    html = """
    <html>
    <head>
        <meta property="og:title" content="OG Title">
        <meta property="og:description" content="OG Description">
        <meta property="og:image" content="https://example.com/image.jpg">
        <meta property="og:url" content="https://example.com">
    </head>
    <body><p>Content</p></body>
    </html>
    """

    options = HtmlOptions(extract_microdata=True)
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    assert "microdata" in doc.metadata
    microdata = doc.metadata["microdata"]

    assert "opengraph" in microdata
    og = microdata["opengraph"]

    assert og["og:title"] == "OG Title"
    assert og["og:description"] == "OG Description"
    assert og["og:image"] == "https://example.com/image.jpg"
    assert og["og:url"] == "https://example.com"


def test_microdata_extraction_twitter_card():
    """Test extraction of Twitter Card metadata."""
    html = """
    <html>
    <head>
        <meta name="twitter:card" content="summary">
        <meta name="twitter:title" content="Tweet Title">
        <meta name="twitter:creator" content="@username">
    </head>
    <body><p>Content</p></body>
    </html>
    """

    options = HtmlOptions(extract_microdata=True)
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    assert "microdata" in doc.metadata
    microdata = doc.metadata["microdata"]

    assert "twitter_card" in microdata
    twitter = microdata["twitter_card"]

    assert twitter["twitter:card"] == "summary"
    assert twitter["twitter:title"] == "Tweet Title"
    assert twitter["twitter:creator"] == "@username"


def test_microdata_extraction_itemscope():
    """Test extraction of HTML microdata with itemscope."""
    html = """
    <div itemscope itemtype="http://schema.org/Person">
        <span itemprop="name">John Doe</span>
        <span itemprop="jobTitle">Software Engineer</span>
    </div>
    """

    options = HtmlOptions(extract_microdata=True)
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    assert "microdata" in doc.metadata
    microdata = doc.metadata["microdata"]

    assert "items" in microdata
    items = microdata["items"]

    assert len(items) > 0
    person = items[0]

    assert person["type"] == "http://schema.org/Person"
    assert person["properties"]["name"] == "John Doe"
    assert person["properties"]["jobTitle"] == "Software Engineer"


def test_microdata_extraction_json_ld():
    """Test extraction of JSON-LD structured data."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Test Article",
            "author": "Jane Smith"
        }
        </script>
    </head>
    <body><p>Content</p></body>
    </html>
    """

    options = HtmlOptions(extract_microdata=True)
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    assert "microdata" in doc.metadata
    microdata = doc.metadata["microdata"]

    assert "json_ld" in microdata
    json_ld = microdata["json_ld"]

    assert len(json_ld) > 0
    article = json_ld[0]

    assert article["@type"] == "Article"
    assert article["headline"] == "Test Article"
    assert article["author"] == "Jane Smith"


def test_microdata_disabled():
    """Test that microdata extraction can be disabled."""
    html = """
    <html>
    <head>
        <meta property="og:title" content="Title">
    </head>
    <body><p>Content</p></body>
    </html>
    """

    options = HtmlOptions(extract_microdata=False)
    converter = HtmlToAstConverter(options)
    doc = converter.parse(html)

    assert "microdata" not in doc.metadata

"""Integration tests for BBCode to Markdown conversion."""

import pytest

from all2md import to_ast, to_markdown
from all2md.ast.nodes import Document


@pytest.mark.integration
def test_bbcode_to_markdown_basic(tmp_path):
    """Test basic BBCode to Markdown conversion."""
    bbcode_content = """[b]This is bold text[/b]

[i]This is italic text[/i]

[u]This is underlined text[/u]

Regular text paragraph."""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "bold text" in result
    assert "italic text" in result
    assert "Regular text" in result


@pytest.mark.integration
def test_bbcode_to_markdown_nested_formatting(tmp_path):
    """Test BBCode with nested formatting."""
    bbcode_content = """[b][i]Bold and italic[/i][/b]

[b]Bold with [i]nested italic[/i] text[/b]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Bold and italic" in result
    assert "nested italic" in result


@pytest.mark.integration
def test_bbcode_to_markdown_links(tmp_path):
    """Test BBCode links conversion."""
    bbcode_content = """[url]https://example.com[/url]

[url=https://example.com]Example Site[/url]

Visit [url=https://github.com]GitHub[/url] for more."""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "https://example.com" in result
    assert "Example Site" in result or "GitHub" in result


@pytest.mark.integration
def test_bbcode_to_markdown_images(tmp_path):
    """Test BBCode images conversion."""
    bbcode_content = """[img]https://example.com/image.jpg[/img]

[img=100x100]https://example.com/thumbnail.jpg[/img]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "https://example.com/image.jpg" in result


@pytest.mark.integration
def test_bbcode_to_markdown_quotes(tmp_path):
    """Test BBCode quotes conversion."""
    bbcode_content = """[quote]This is a quoted text.[/quote]

[quote=Alice]This is Alice's quote.[/quote]

[quote author=Bob]Bob said this.[/quote]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "quoted text" in result


@pytest.mark.integration
def test_bbcode_to_markdown_code_blocks(tmp_path):
    """Test BBCode code blocks conversion."""
    bbcode_content = """[code]
def hello():
    return "Hello, World!"
[/code]

Inline [code]code[/code] example.

[code=python]
def greet(name):
    return f"Hello, {name}!"
[/code]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "def hello():" in result
    assert "Hello, World!" in result


@pytest.mark.integration
def test_bbcode_to_markdown_lists(tmp_path):
    """Test BBCode lists conversion."""
    bbcode_content = """[list]
[*]Item 1
[*]Item 2
[*]Item 3
[/list]

[list=1]
[*]First item
[*]Second item
[*]Third item
[/list]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Item 1" in result
    assert "Item 2" in result
    assert "First item" in result


@pytest.mark.integration
def test_bbcode_to_markdown_colors(tmp_path):
    """Test BBCode color tags (may be stripped or preserved)."""
    bbcode_content = """[color=red]Red text[/color]

[color=#0000FF]Blue text[/color]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Colors may not be preserved in Markdown
    assert "Red text" in result
    assert "Blue text" in result


@pytest.mark.integration
def test_bbcode_to_markdown_sizes(tmp_path):
    """Test BBCode size tags."""
    bbcode_content = """[size=10]Small text[/size]

[size=20]Large text[/size]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Sizes may not be preserved in Markdown
    assert "Small text" in result
    assert "Large text" in result


@pytest.mark.integration
def test_bbcode_to_markdown_headings(tmp_path):
    """Test BBCode-style headings if supported."""
    bbcode_content = """[h1]Main Heading[/h1]

[h2]Subheading[/h2]

[h3]Sub-subheading[/h3]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # May or may not have BBCode heading support
    assert "Main Heading" in result
    assert "Subheading" in result


@pytest.mark.integration
def test_bbcode_to_markdown_center_align(tmp_path):
    """Test BBCode center alignment."""
    bbcode_content = """[center]Centered text[/center]

[left]Left-aligned text[/left]

[right]Right-aligned text[/right]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Alignment may not be preserved in Markdown
    assert "Centered text" in result
    assert "Left-aligned text" in result


@pytest.mark.integration
def test_bbcode_to_markdown_strikethrough(tmp_path):
    """Test BBCode strikethrough."""
    bbcode_content = """[s]Strikethrough text[/s]

[strike]Another strikethrough[/strike]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Strikethrough text" in result
    assert "Another strikethrough" in result


@pytest.mark.integration
def test_bbcode_to_markdown_nested_lists(tmp_path):
    """Test BBCode nested lists."""
    bbcode_content = """[list]
[*]Item 1
[list]
[*]Sub-item 1.1
[*]Sub-item 1.2
[/list]
[*]Item 2
[/list]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Item 1" in result
    assert "Sub-item 1.1" in result


@pytest.mark.integration
def test_bbcode_to_markdown_tables(tmp_path):
    """Test BBCode tables if supported."""
    bbcode_content = """[table]
[tr][th]Name[/th][th]Age[/th][th]City[/th][/tr]
[tr][td]Alice[/td][td]30[/td][td]NYC[/td][/tr]
[tr][td]Bob[/td][td]25[/td][td]LA[/td][/tr]
[/table]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Tables may or may not be supported in BBCode parser
    assert "Name" in result
    assert "Alice" in result


@pytest.mark.integration
def test_bbcode_to_markdown_mixed_content(tmp_path):
    """Test BBCode with mixed formatting."""
    bbcode_content = """[b]Bold[/b] and [i]italic[/i] and [u]underline[/u].

[url=https://example.com]A [b]bold[/b] link[/url]

[quote]
This is a quote with [b]bold[/b] text.
[/quote]

[code]
if (condition) {
    do_something();
}
[/code]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Bold" in result
    assert "italic" in result
    assert "https://example.com" in result


@pytest.mark.integration
def test_bbcode_to_markdown_spoiler(tmp_path):
    """Test BBCode spoiler tags."""
    bbcode_content = """[spoiler]Hidden content[/spoiler]

[spoiler=Click to reveal]Secret information[/spoiler]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Spoilers may be converted to regular text or special formatting
    assert "Hidden content" in result or "Secret information" in result


@pytest.mark.integration
def test_bbcode_to_markdown_youtube_embed(tmp_path):
    """Test BBCode YouTube embed tags."""
    bbcode_content = """[youtube]dQw4w9WgXcQ[/youtube]

[video=youtube]https://www.youtube.com/watch?v=dQw4w9WgXcQ[/video]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Video embeds may be converted to links
    assert isinstance(result, str)


@pytest.mark.integration
def test_bbcode_to_markdown_unicode_content(tmp_path):
    """Test BBCode with Unicode characters."""
    bbcode_content = """[b]Unicode Test \U0001f600[/b]

Chinese: \U00004e2d\U00006587
Greek: \U00000391\U000003b1
Emoji: \U0001f600 \U00002764 \U00002b50"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Unicode Test" in result


@pytest.mark.integration
def test_bbcode_to_markdown_malformed_tags(tmp_path):
    """Test BBCode with malformed or unclosed tags."""
    bbcode_content = """[b]Unclosed bold tag

[i]Italic [b]with nested bold[/i][/b]

[url]Invalid URL tag"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Should handle gracefully without crashing
    assert isinstance(result, str)


@pytest.mark.integration
def test_bbcode_to_markdown_escaped_brackets(tmp_path):
    """Test BBCode with escaped brackets."""
    bbcode_content = """This text has \\[not a tag\\] in it.

[b]This is bold[/b] but \\[b\\]this is not\\[/b\\]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Escaped brackets should be handled
    assert isinstance(result, str)


@pytest.mark.integration
def test_bbcode_to_ast_conversion(tmp_path):
    """Test BBCode to AST conversion pipeline."""
    bbcode_content = """[b]AST Test[/b]

[i]Testing AST conversion for BBCode.[/i]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    doc = to_ast(bbcode_file)

    # Verify AST structure
    assert isinstance(doc, Document)

    # Verify content through markdown conversion
    result = to_markdown(bbcode_file)
    assert "AST Test" in result


@pytest.mark.integration
def test_bbcode_to_markdown_empty_tags(tmp_path):
    """Test BBCode with empty tags."""
    bbcode_content = """[b][/b]

[i][/i]

[url][/url]

Regular text."""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Empty tags should be handled gracefully
    assert "Regular text" in result


@pytest.mark.integration
def test_bbcode_to_markdown_case_insensitive_tags(tmp_path):
    """Test BBCode with mixed case tags."""
    bbcode_content = """[B]Bold with uppercase[/B]

[I]Italic with uppercase[/I]

[URL=https://example.com]Mixed case URL[/URL]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # BBCode tags are typically case-insensitive
    assert "Bold with uppercase" in result
    assert "Italic with uppercase" in result


@pytest.mark.integration
def test_bbcode_to_markdown_whitespace_handling(tmp_path):
    """Test BBCode whitespace handling."""
    bbcode_content = """[b]  Bold with spaces  [/b]

[ i ]Italic with spaces in tags[ /i ]

[code]
    Indented code
    More indented code
[/code]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    # Should handle whitespace appropriately
    assert isinstance(result, str)


@pytest.mark.integration
def test_bbcode_to_markdown_long_content(tmp_path):
    """Test BBCode with long content."""
    paragraphs = [f"[b]Paragraph {i}:[/b] This is a long paragraph with lots of content." for i in range(50)]
    bbcode_content = "\n\n".join(paragraphs)

    bbcode_file = tmp_path / "long.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Paragraph 0:" in result
    assert "Paragraph 49:" in result


@pytest.mark.integration
def test_bbcode_to_markdown_special_characters(tmp_path):
    """Test BBCode with special characters in content."""
    bbcode_content = """[b]Special chars: & < > " '[/b]

[code]Code with <html> tags & symbols[/code]"""

    bbcode_file = tmp_path / "test.bbcode"
    bbcode_file.write_text(bbcode_content, encoding="utf-8")

    result = to_markdown(bbcode_file)

    assert "Special chars" in result

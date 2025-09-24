from mdparse.html2markdown import HTMLToMarkdown, html_to_markdown


def test_heading_hash_true():
    html = "<h1>Title</h1><h2>Sub</h2>"
    converter = HTMLToMarkdown(hash_headings=True)
    md = converter.convert(html)
    assert md == "# Title\n\n## Sub"


def test_heading_hash_false():
    html = "<h1>Title</h1><h2>Sub</h2>"
    converter = HTMLToMarkdown(hash_headings=False)
    md = converter.convert(html)
    assert md == "Title\n=====\n\nSub\n---"


def test_paragraph_and_inline_formatting():
    html = "<p>This is <strong>bold</strong>, <em>italic</em>, and <code>code</code>.</p>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "This is **bold**, *italic*, and `code`."


def test_line_break_and_horizontal_rule():
    html = "Line1<br>Line2<hr>Line3"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "Line1\nLine2\n\n---\n\nLine3"


def test_unordered_list_simple():
    html = "<ul><li>One</li><li>Two</li></ul>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "* One\n* Two"


def test_ordered_list_simple():
    html = "<ol><li>First</li><li>Second</li></ol>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "1. First\n2. Second"


def test_unordered_list_nested():
    html = "<ul><li>Parent<ul><li>Child</li></ul></li></ul>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "* Parent\n  - Child"


def test_ordered_list_nested():
    html = "<ol><li>Parent<ol><li>Child</li></ol></li></ol>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "1. Parent\n   1. Child"


def test_mixed_list_symbols_and_depth():
    html = "<ul><li>A<ul><li>B<ol><li>C</li></ol></li></ul></li></ul>"
    converter = HTMLToMarkdown(bullet_symbols="*+")
    md = converter.convert(html)
    expected = "* A\n  + B\n     1. C"
    assert md == expected


def test_link_with_and_without_title():
    html_title = '<a href="http://example.com" title="T">link</a>'
    html_no_title = '<a href="http://example.com">link</a>'
    converter = HTMLToMarkdown()
    md1 = converter.convert(html_title)
    md2 = converter.convert(html_no_title)
    assert md1 == '[link](http://example.com "T")'
    assert md2 == "[link](http://example.com)"


def test_image_and_removal():
    html = '<img src="img.png" alt="Alt" title="T">'
    conv_keep = HTMLToMarkdown(remove_images=False)
    conv_remove = HTMLToMarkdown(remove_images=True)
    assert conv_keep.convert(html) == '![Alt](img.png "T")'
    assert conv_remove.convert(html) == ""


def test_code_block_language_class():
    html = '<pre class="python"><code>print("hi")</code></pre>'
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == '```python\nprint("hi")\n```'


def test_inline_code_and_special_characters():
    html = "<p>* _ ` # + - . ! [ ] ( ) { } \\</p>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "* _ ` # + - . ! [ ] ( ) { } \\"


def test_blockquote_simple():
    html = "<blockquote>Quote</blockquote>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "> Quote"


def test_table_with_header_and_rows():
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    expected = "| A | B |\n|:---:|:---:|\n| 1 | 2 |"
    assert md == expected


def test_mixed_content_div():
    html = "<div><p>X</p><ul><li><em>I</em></li></ul></div>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "X\n\n* *I*"


def test_empty_elements():
    conv = HTMLToMarkdown()
    assert conv.convert("<p></p>") == ""
    assert conv.convert("<ul><li></li></ul>") == ""


def test_custom_emphasis_symbol_and_bullets():
    html = "<p><em>italic</em> <strong>bold</strong></p><ul><li>One</li></ul>"
    converter = HTMLToMarkdown(emphasis_symbol="_", bullet_symbols="x")
    md = converter.convert(html)
    assert md == "_italic_ __bold__\n\nx One"


def test_title_extraction_default_and_no_hash():
    html = "<html><head><title>My Title</title></head><body><p>Para</p></body></html>"
    md_default = html_to_markdown(html, extract_title=True)
    assert md_default == "# My Title\n\nPara"
    md_no_hash = html_to_markdown(html, use_hash_headings=False, extract_title=True)
    assert md_no_hash == "My Title\n========\n\nPara"


def test_html_to_markdown_alias():
    assert html_to_markdown("<p>Hi</p>") == "Hi"

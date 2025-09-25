"""Advanced tests for HTML nested element handling edge cases."""


from all2md.html2markdown import HTMLToMarkdown, html_to_markdown
from all2md.options import HtmlOptions
from tests.utils import assert_markdown_valid


class TestHtmlNestedElements:
    """Test complex nested element scenarios in HTML documents."""

    def test_nested_emphasis_combinations(self):
        """Test complex nested emphasis/formatting combinations."""
        html = """
        <p>Text with <strong>bold and <em>italic and <code>code</code></em></strong> nesting</p>
        <p><em>Italic with <strong>bold</strong> and <a href="http://example.com">link</a></em></p>
        <p><code>Code with <strong>bold inside code</strong></code></p>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle nested formatting appropriately
        assert "**" in markdown  # Bold formatting
        assert "*" in markdown   # Italic formatting
        assert "`" in markdown   # Code formatting
        assert "[link]" in markdown  # Link formatting

        # Check specific nesting patterns
        assert "code" in markdown
        assert "bold" in markdown
        assert "italic" in markdown

    def test_nested_lists_and_blockquotes(self):
        """Test complex nesting of lists and blockquotes."""
        html = """
        <blockquote>
            <p>Quote with <em>emphasis</em></p>
            <ul>
                <li>List in quote
                    <blockquote>
                        <p>Nested quote in list</p>
                        <ol>
                            <li>Ordered in quote in list</li>
                            <li>Second ordered item</li>
                        </ol>
                    </blockquote>
                </li>
                <li>Second list item in quote</li>
            </ul>
            <p>More quote content</p>
        </blockquote>
        """

        options = HtmlOptions(preserve_nested_structure=True)
        markdown = html_to_markdown(html, options=options)
        assert_markdown_valid(markdown)

        # Should preserve blockquote structure
        assert "> " in markdown

        # Should handle nested lists
        assert "* " in markdown or "- " in markdown  # Unordered list
        assert "1. " in markdown  # Ordered list

        # Content should be preserved
        assert "emphasis" in markdown
        assert "List in quote" in markdown
        assert "Nested quote" in markdown
        assert "Ordered in quote" in markdown

    def test_deeply_nested_lists(self):
        """Test deeply nested list structures."""
        html = """
        <ul>
            <li>Level 1
                <ul>
                    <li>Level 2
                        <ol>
                            <li>Level 3 ordered
                                <ul>
                                    <li>Level 4
                                        <ul>
                                            <li>Level 5 deep</li>
                                        </ul>
                                    </li>
                                </ul>
                            </li>
                        </ol>
                    </li>
                </ul>
            </li>
        </ul>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle deep nesting
        lines = markdown.split('\n')
        list_lines = [line for line in lines if line.strip() and (
            line.strip().startswith('*') or
            line.strip().startswith('-') or
            line.strip().startswith('1.')
        )]

        assert len(list_lines) >= 5  # Should have all levels

        # Check increasing indentation
        indentations = [len(line) - len(line.lstrip()) for line in list_lines]
        assert max(indentations) > min(indentations)  # Should have varying indentation

    def test_mixed_content_in_containers(self):
        """Test mixed content types within container elements."""
        html = """
        <div>
            <h2>Section Header</h2>
            <p>Paragraph with <code>inline code</code> and <strong>bold text</strong></p>
            <ul>
                <li><strong>Bold list item</strong> with <a href="#anchor">anchor link</a></li>
                <li><em>Italic</em> with <code>code</code> and <del>strikethrough</del></li>
            </ul>
            <blockquote>
                <p>Quote with <em>emphasis</em></p>
                <pre><code>Code block in quote</code></pre>
            </blockquote>
        </div>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should contain all content types
        assert "## Section Header" in markdown
        assert "**bold text**" in markdown
        assert "`inline code`" in markdown
        assert "**Bold list item**" in markdown
        assert "[anchor link](#anchor)" in markdown
        assert "*Italic*" in markdown
        assert "~~strikethrough~~" in markdown or "strikethrough" in markdown
        assert "> " in markdown  # Blockquote
        assert "```" in markdown or "`" in markdown  # Code block

    def test_nested_links_and_images(self):
        """Test nested links and images in various contexts."""
        html = """
        <p>Text with <a href="http://example.com">link containing <img src="icon.png" alt="icon"> image</a></p>
        <ul>
            <li><a href="/page1">Link in list</a> with <img src="bullet.png" alt="bullet"></li>
            <li><img src="image1.png" alt="Image"> followed by <a href="/page2">link</a></li>
        </ul>
        <blockquote>
            <p>Quote with <a href="http://quoted.com">quoted link</a></p>
            <p><img src="quoted-image.png" alt="Quoted image"></p>
        </blockquote>
        """

        converter = HTMLToMarkdown(attachment_mode="alt_text")
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle links and images in different contexts
        assert "[link" in markdown  # Link text
        assert "![icon]" in markdown  # Image alt text
        assert "![bullet]" in markdown
        assert "![Image]" in markdown
        assert "[quoted link]" in markdown
        assert "![Quoted image]" in markdown

    def test_table_within_other_elements(self):
        """Test tables nested within other elements."""
        html = """
        <div>
            <h3>Data Section</h3>
            <table>
                <tr><th>Name</th><th>Value</th></tr>
                <tr><td>Item 1</td><td>100</td></tr>
                <tr><td>Item 2</td><td>200</td></tr>
            </table>
            <p>Table description</p>
        </div>
        <li>
            List item with table:
            <table>
                <tr><td>A</td><td>B</td></tr>
                <tr><td>1</td><td>2</td></tr>
            </table>
        </li>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should contain table structure
        assert "| Name | Value |" in markdown
        assert "| Item 1 | 100 |" in markdown
        assert "| A | B |" in markdown
        assert "### Data Section" in markdown
        assert "Table description" in markdown

    def test_code_blocks_with_nested_content(self):
        """Test code blocks containing various content."""
        html = """
        <pre><code>def function():
    # This is a comment with <em>HTML</em> that should not be processed
    return "string with &amp; entity"</code></pre>

        <p>Inline code: <code>var x = &lt;tag&gt;;</code></p>

        <pre class="python"><code>
# Python code with HTML-like content
def parse_html():
    html = "&lt;p&gt;Hello &amp; goodbye&lt;/p&gt;"
    return html
        </code></pre>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve code content without processing HTML
        assert "def function():" in markdown
        assert "string with & entity" in markdown  # Entities should be decoded
        assert "var x = <tag>;" in markdown  # Entities should be decoded
        assert "```python" in markdown
        assert "parse_html" in markdown

    def test_definition_lists_with_complex_content(self):
        """Test definition lists with complex nested content."""
        html = """
        <dl>
            <dt>Term with <strong>formatting</strong></dt>
            <dd>Definition with <em>emphasis</em> and <a href="/link">link</a>
                <ul>
                    <li>List in definition</li>
                    <li>Another item</li>
                </ul>
            </dd>
            <dt>Code Term</dt>
            <dd>
                <pre><code>Code block in definition</code></pre>
                <p>Followed by paragraph</p>
            </dd>
        </dl>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle definition lists with complex content
        assert "**formatting**" in markdown
        assert "*emphasis*" in markdown
        assert "[link](/link)" in markdown
        assert "List in definition" in markdown
        assert "Code block" in markdown

    def test_form_elements_and_inputs(self):
        """Test handling of form elements and inputs."""
        html = """
        <form>
            <label for="name">Name: <input type="text" id="name" placeholder="Enter name"></label>
            <p>Description with <strong>formatting</strong></p>
            <select name="options">
                <option value="1">Option 1</option>
                <option value="2">Option 2</option>
            </select>
            <textarea placeholder="Comments">Default text</textarea>
            <button type="submit">Submit <em>Form</em></button>
        </form>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Form elements might be preserved as text or omitted
        # The key is that it doesn't break the conversion
        assert "**formatting**" in markdown  # Should preserve text formatting
        # Form-specific content handling depends on implementation

    def test_nested_headings_and_sections(self):
        """Test nested heading structures and sections."""
        html = """
        <section>
            <h1>Main Title</h1>
            <div>
                <h2>Subsection with <em>italic</em></h2>
                <p>Content under h2</p>
                <article>
                    <h3>Article Title</h3>
                    <p>Article content with <strong>bold</strong></p>
                    <aside>
                        <h4>Sidebar</h4>
                        <p>Sidebar content</p>
                    </aside>
                </article>
            </div>
        </section>
        """

        converter = HTMLToMarkdown(hash_headings=True)
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve heading hierarchy
        assert "# Main Title" in markdown
        assert "## Subsection" in markdown
        assert "### Article Title" in markdown
        assert "#### Sidebar" in markdown

        # Should preserve formatting in headings
        assert "*italic*" in markdown
        assert "**bold**" in markdown

    def test_media_elements_with_content(self):
        """Test media elements (audio, video) with fallback content."""
        html = """
        <video controls>
            <source src="movie.mp4" type="video/mp4">
            <p>Your browser doesn't support video. <a href="movie.mp4">Download instead</a></p>
        </video>

        <audio controls>
            <source src="audio.mp3" type="audio/mpeg">
            <p>Audio not supported. <a href="audio.mp3">Download audio</a></p>
        </audio>

        <object data="document.pdf" type="application/pdf">
            <p>PDF cannot be displayed. <a href="document.pdf">Download PDF</a></p>
        </object>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve fallback content
        assert "Download instead" in markdown
        assert "Download audio" in markdown
        assert "Download PDF" in markdown

    def test_ruby_annotations_and_specialized_elements(self):
        """Test ruby annotations and other specialized HTML elements."""
        html = """
        <p>Japanese text: <ruby>漢字<rt>かんじ</rt></ruby></p>
        <p>Abbreviation: <abbr title="HyperText Markup Language">HTML</abbr></p>
        <p>Citation: <cite>Book Title</cite> by Author</p>
        <p>Keyboard input: <kbd>Ctrl+C</kbd></p>
        <p>Sample output: <samp>Error: File not found</samp></p>
        <p>Variable: <var>x</var> = 42</p>
        <p>Time: <time datetime="2023-12-25">Christmas Day</time></p>
        """

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve text content appropriately
        assert "漢字" in markdown
        assert "HTML" in markdown
        assert "Book Title" in markdown
        assert "Ctrl+C" in markdown
        assert "Error: File not found" in markdown
        assert "Christmas Day" in markdown

"""Advanced tests for HTML code block handling edge cases."""

from all2md.converters.html2markdown import HTMLToMarkdown
from tests.utils import assert_markdown_valid


class TestHtmlCodeBlocks:
    """Test complex code block scenarios in HTML documents."""

    def test_code_fence_with_backticks_in_content(self):
        """Test code blocks containing backticks in the content."""
        html = '''<pre><code>Use ```markdown``` syntax for code blocks.
Multiple ``` backticks ``` in content.
Even `````five````` backticks in a row.</code></pre>'''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should use appropriate fence length to avoid conflicts
        assert "```" in markdown or "````" in markdown or "`````" in markdown
        assert "markdown" in markdown
        assert "backticks" in markdown

    def test_nested_code_in_different_elements(self):
        """Test code blocks nested within different HTML elements."""
        html = '''
        <div>
            <h3>Code Examples</h3>
            <pre><code>def function():
    return "block code"</code></pre>
            <p>With inline <code>code</code> as well.</p>
        </div>

        <blockquote>
            <p>Quote with code:</p>
            <pre class="python"><code>print("quoted code")</code></pre>
        </blockquote>

        <ul>
            <li>List with <code>inline code</code></li>
            <li>List with block:
                <pre><code>list_code = True</code></pre>
            </li>
        </ul>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle code in different contexts
        assert "def function" in markdown
        assert "`code`" in markdown  # Inline code
        assert "quoted code" in markdown
        assert "`inline code`" in markdown
        assert "list_code" in markdown
        assert "### Code Examples" in markdown
        assert "> " in markdown  # Blockquote

    def test_language_specification_variations(self):
        """Test various ways of specifying code block languages."""
        html = '''
        <pre class="language-python"><code>def python_func():
    pass</code></pre>

        <pre class="lang-javascript"><code>function jsFunc() {
    return true;
}</code></pre>

        <pre class="brush: sql"><code>SELECT * FROM table;</code></pre>

        <pre data-lang="rust"><code>fn main() {
    println!("Hello");
}</code></pre>

        <pre><code class="language-go">func main() {
    fmt.Println("Go")
}</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should detect and use language specifications
        assert "```python" in markdown
        assert "```javascript" in markdown or "```js" in markdown
        assert "```sql" in markdown
        assert "```rust" in markdown or "```" in markdown  # Fallback
        assert "```go" in markdown

        # Should preserve code content
        assert "python_func" in markdown
        assert "jsFunc" in markdown
        assert "SELECT" in markdown
        assert "println!" in markdown
        assert "fmt.Println" in markdown

    def test_code_blocks_with_html_entities(self):
        """Test code blocks containing HTML entities."""
        html = '''
        <pre><code>if (x &lt; y &amp;&amp; y &gt; z) {
    console.log("condition &amp; result");
    return "&lt;tag&gt;";
}</code></pre>

        <pre class="xml"><code>&lt;?xml version="1.0"?&gt;
&lt;root&gt;
    &lt;item value="&amp;quot;test&amp;quot;"&gt;Content&lt;/item&gt;
&lt;/root&gt;</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should decode HTML entities in code blocks
        assert "<" in markdown and ">" in markdown
        assert "&" in markdown
        assert '"test"' in markdown
        assert "<?xml" in markdown

    def test_mixed_inline_and_block_code(self):
        """Test documents with both inline and block code."""
        html = '''
        <p>Use the <code>print()</code> function like this:</p>

        <pre><code>print("Hello, World!")
print("Multiple lines")
# Comment with `backticks`</code></pre>

        <p>Or use <code>`backticks`</code> for inline code with <code>multiple `embedded` backticks</code>.</p>

        <pre class="python"><code>def example():
    """Docstring with `backticks`"""
    return f"formatted {string}"</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle both inline and block code appropriately
        assert "`print()`" in markdown  # Inline code
        assert "```" in markdown  # Block code
        assert "Hello, World!" in markdown
        assert "`backticks`" in markdown
        assert "embedded" in markdown
        assert "def example" in markdown

    def test_code_blocks_with_special_characters(self):
        """Test code blocks containing various special characters."""
        html = '''
        <pre><code>// Special characters test
const regex = /[.*+?^${}()|[\\]\\]/g;
const template = `Template with ${variable}`;
const symbols = "!@#$%^&*()_+-=[]{}|;':\",./<>?";
const unicode = "émojis: 🚀 🎉 ✨";</code></pre>

        <pre class="bash"><code>#!/bin/bash
echo "Bash script with special chars: $HOME & $(whoami)"
grep -E '^[A-Z]+$' file.txt | sort > output.txt</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve special characters in code
        assert "regex" in markdown
        assert "${variable}" in markdown
        assert "!@#$%^&*" in markdown
        assert "🚀" in markdown
        assert "$HOME" in markdown
        assert "grep -E" in markdown

    def test_empty_and_whitespace_code_blocks(self):
        """Test empty or whitespace-only code blocks."""
        html = '''
        <pre><code></code></pre>

        <pre><code>   </code></pre>

        <pre><code>


        </code></pre>

        <p>Between empty blocks</p>

        <pre><code>actual_code = True</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should handle empty blocks gracefully
        assert "Between empty blocks" in markdown
        assert "actual_code" in markdown

        # Empty blocks might be omitted or preserved as empty
        lines = markdown.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        assert len(non_empty_lines) >= 2  # Should have content

    def test_code_blocks_in_tables(self):
        """Test code blocks within table cells."""
        html = '''
        <table>
            <tr>
                <th>Function</th>
                <th>Example</th>
            </tr>
            <tr>
                <td><code>print()</code></td>
                <td><pre><code>print("hello")</code></pre></td>
            </tr>
            <tr>
                <td>Loop</td>
                <td><pre><code>for i in range(10):
    print(i)</code></pre></td>
            </tr>
        </table>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should maintain table structure with code
        assert "| Function | Example |" in markdown
        assert "`print()`" in markdown
        assert "print(\"hello\")" in markdown
        assert "for i in range" in markdown

    def test_code_with_line_numbers_and_highlighting(self):
        """Test code blocks with line numbers or syntax highlighting markup."""
        html = '''
        <pre class="line-numbers language-python"><code><span class="line-number">1</span>def function():
<span class="line-number">2</span>    <span class="keyword">return</span> <span class="string">"highlighted"</span>
<span class="line-number">3</span>    <span class="comment"># Comment</span></code></pre>

        <pre><code><span class="hljs-function"><span class="hljs-keyword">function</span> <span class="hljs-title">example</span>() {</span>
    <span class="hljs-keyword">return</span> <span class="hljs-string">"code"</span>;
<span class="hljs-punctuation">}</span></code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should extract plain code content, ignoring markup
        assert "def function" in markdown
        assert "return" in markdown
        assert "highlighted" in markdown
        assert "Comment" in markdown
        assert "function example" in markdown

    def test_code_blocks_with_tabs_and_spaces(self):
        """Test code blocks with mixed tabs and spaces for indentation."""
        html = '''
        <pre><code>def mixed_indentation():
    if True:
\t\treturn "tabs"
    else:
        return "spaces"
\t# Mixed comment</code></pre>

        <pre class="python"><code>class Example:
\tdef __init__(self):
\t\tself.value = 42

    def method(self):
\t    return self.value</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve indentation (tabs might be converted to spaces)
        assert "def mixed_indentation" in markdown
        assert "return \"tabs\"" in markdown
        assert "return \"spaces\"" in markdown
        assert "class Example" in markdown
        assert "self.value = 42" in markdown

    def test_code_blocks_with_urls_and_links(self):
        """Test code blocks containing URLs and link-like content."""
        html = '''
        <pre><code># Configuration
API_URL = "https://api.example.com/v1"
DOCS_URL = "http://docs.example.com"

# Markdown example
link = "[Example](https://example.com)"
image = "![alt](https://example.com/image.png)"</code></pre>

        <pre class="bash"><code>curl -X GET "https://api.github.com/users/octocat" \
     -H "Accept: application/vnd.github+json"
wget http://example.com/file.tar.gz</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve URLs in code without converting to links
        assert "https://api.example.com" in markdown
        assert "http://docs.example.com" in markdown
        assert "[Example](https://example.com)" in markdown
        assert "curl -X GET" in markdown
        assert "wget http://example.com" in markdown

    def test_code_blocks_with_mathematical_content(self):
        """Test code blocks containing mathematical or scientific content."""
        html = '''
        <pre class="python"><code># Mathematical calculations
import math

def calculate_area(radius):
    return math.pi * radius ** 2

# Scientific notation
avogadro = 6.022e23
planck = 6.626e-34

# LaTeX-like content in comments
# Formula: E = mc²
# Integral: ∫₀^∞ e^(-x²) dx = √π/2</code></pre>
        '''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html)
        assert_markdown_valid(markdown)

        # Should preserve mathematical content
        assert "math.pi" in markdown
        assert "6.022e23" in markdown
        assert "6.626e-34" in markdown
        assert "E = mc²" in markdown
        assert "∫₀^∞" in markdown

    def test_dynamic_fence_selection(self):
        """Test that appropriate fence lengths are chosen based on content."""
        html_simple = '<pre><code>simple code</code></pre>'
        html_backticks = '<pre><code>Use ```markdown``` syntax</code></pre>'
        html_four_backticks = '<pre><code>Code with ````four backticks````</code></pre>'
        html_many_backticks = '<pre><code>Many `````` backticks ``````</code></pre>'

        converter = HTMLToMarkdown()

        md_simple = converter.convert(html_simple)
        md_backticks = converter.convert(html_backticks)
        md_four = converter.convert(html_four_backticks)
        md_many = converter.convert(html_many_backticks)

        # Should use appropriate fence lengths
        assert md_simple.count('`') >= 6  # At least ``` opening and closing
        assert "````" in md_backticks or "`````" in md_backticks  # Longer than content
        assert "`````" in md_four or "``````" in md_four  # Longer than content backticks
        assert md_many.count('`') > 12  # Should use even longer fences

    def test_boundary_fence_lengths(self):
        """Test fence length boundary conditions with 7-10 backticks in content."""
        # Test 7 backticks in content
        html_seven = '<pre><code>Code with ```````seven backticks```````</code></pre>'

        # Test 8 backticks in content
        html_eight = '<pre><code>Code with ````````eight backticks````````</code></pre>'

        # Test 9 backticks in content
        html_nine = '<pre><code>Code with `````````nine backticks`````````</code></pre>'

        # Test 10 backticks in content (maximum fence length)
        html_ten = '<pre><code>Code with ``````````ten backticks``````````</code></pre>'

        # Test 11 backticks in content (exceeds maximum fence length)
        html_eleven = '<pre><code>Code with ```````````eleven backticks```````````</code></pre>'

        converter = HTMLToMarkdown()

        md_seven = converter.convert(html_seven)
        md_eight = converter.convert(html_eight)
        md_nine = converter.convert(html_nine)
        md_ten = converter.convert(html_ten)
        md_eleven = converter.convert(html_eleven)

        # Should use 8 backticks for fencing when content has 7
        assert "````````" in md_seven
        assert "```````seven backticks```````" in md_seven

        # Should use 9 backticks for fencing when content has 8
        assert "`````````" in md_eight
        assert "````````eight backticks````````" in md_eight

        # Should use 10 backticks for fencing when content has 9
        assert "``````````" in md_nine
        assert "`````````nine backticks`````````" in md_nine

        # Should use 10 backticks (maximum) for fencing when content has 10
        assert "``````````" in md_ten
        assert "``````````ten backticks``````````" in md_ten

        # Should use 10 backticks (maximum) even when content has 11
        # This tests the MAX_CODE_FENCE_LENGTH boundary
        assert "``````````" in md_eleven
        assert "```````````eleven backticks```````````" in md_eleven

    def test_mixed_backtick_sequences(self):
        """Test code containing mixed sequences of different backtick lengths."""
        html_mixed = '''<pre><code>Mixed backticks:
`single`
``double``
```triple```
````quad````
`````five`````
``````six``````
```````seven```````
````````eight````````</code></pre>'''

        converter = HTMLToMarkdown()
        markdown = converter.convert(html_mixed)
        assert_markdown_valid(markdown)

        # Should use 9 backticks to fence content containing up to 8
        assert "`````````" in markdown
        assert "````````eight````````" in markdown

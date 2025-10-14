"""Advanced tests for HTML entity handling edge cases."""

from utils import assert_markdown_valid

from all2md import HtmlOptions
from all2md import to_markdown as html_to_markdown


class TestHtmlEntities:
    """Test complex HTML entity scenarios."""

    def test_common_html_entities(self):
        """Test common HTML entities and their conversion."""
        html = '''
        <p>Common entities: &amp; &lt; &gt; &quot; &#39;</p>
        <p>Copyright &copy; and trademark &trade;</p>
        <p>Registered &reg; and section &sect;</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode common entities
        assert "&" in markdown
        assert "<" in markdown
        assert ">" in markdown
        assert '"' in markdown
        assert "'" in markdown
        assert "©" in markdown
        assert "™" in markdown
        assert "®" in markdown
        assert "§" in markdown

    def test_numeric_character_references(self):
        """Test numeric character references (decimal and hexadecimal)."""
        html = '''
        <p>Decimal: &#8230; &#8482; &#169; &#8364;</p>
        <p>Hexadecimal: &#x2026; &#x2122; &#xA9; &#x20AC;</p>
        <p>Mixed: &#65; &#x42; &#67; &#x44;</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode numeric references
        assert "…" in markdown  # Ellipsis
        assert "™" in markdown  # Trademark
        assert "©" in markdown  # Copyright
        assert "€" in markdown  # Euro
        assert "A" in markdown and "B" in markdown and "C" in markdown and "D" in markdown  # Letters

    def test_special_spacing_entities(self):
        """Test special spacing and whitespace entities."""
        html = '''
        <p>Non-breaking&nbsp;spaces&nbsp;here</p>
        <p>Em&mdash;dash and en&ndash;dash</p>
        <p>Thin&thinsp;space and hair&hairsp;space</p>
        <p>Zero&zwnj;width&zwj;joiners</p>
        '''

        options_preserve = HtmlOptions(convert_nbsp=True)
        options_no_preserve = HtmlOptions(convert_nbsp=False)

        md_preserve = html_to_markdown(html, parser_options=options_preserve, source_format="html")
        md_no_preserve = html_to_markdown(html, parser_options=options_no_preserve, source_format="html")

        assert_markdown_valid(md_preserve)
        assert_markdown_valid(md_no_preserve)

        # Should handle non-breaking spaces appropriately
        assert "spaces" in md_preserve
        assert "spaces" in md_no_preserve

        # Should decode dashes
        assert "—" in md_preserve or "—" in md_no_preserve  # Em dash
        assert "–" in md_preserve or "–" in md_no_preserve  # En dash

    def test_entities_in_different_contexts(self):
        """Test entities in various HTML contexts."""
        html = '''
        <h1>Title with &amp; entity</h1>
        <p><strong>Bold &amp; italic</strong> text</p>
        <code>Code with &lt;tags&gt;</code>
        <a href="mailto:test@example.com?subject=Test&amp;body=Hello">Email with &amp;</a>
        <pre><code>if (x &lt; y &amp;&amp; y &gt; z) {
    return "&lt;result&gt;";
}</code></pre>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode entities in all contexts
        assert "# Title with & entity" in markdown
        assert "**Bold & italic**" in markdown
        assert "`Code with <tags>`" in markdown
        assert "test@example.com" in markdown
        assert "< y && y >" in markdown

    def test_entities_in_attributes(self):
        """Test entities in HTML attributes."""
        html = '''
        <a href="http://example.com?param=value&amp;other=data" title="Link &amp; title">Link text</a>
        <img src="image.png" alt="Image &amp; description" title="Tooltip &amp; info">
        <abbr title="HyperText &amp; Markup Language">HTML</abbr>
        '''

        markdown = html_to_markdown(html, parser_options=HtmlOptions(attachment_mode="alt_text"), source_format="html")
        assert_markdown_valid(markdown)

        # Should handle entities in attributes
        assert "[Link text]" in markdown
        assert "![Image & description]" in markdown or "![Image" in markdown
        assert "HTML" in markdown

    def test_malformed_and_invalid_entities(self):
        """Test handling of malformed or invalid entities."""
        html = '''
        <p>Invalid: &invalid; &amp &lt &gt</p>
        <p>Incomplete: &#123 &#x4 &copy</p>
        <p>Mixed: Valid &amp; invalid &badentity; text</p>
        <p>Numbers: &#999999; &#xFFFFF;</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle invalid entities gracefully
        assert "Invalid:" in markdown
        assert "Incomplete:" in markdown
        assert "Valid & invalid" in markdown
        assert "Mixed:" in markdown

    def test_entities_with_mathematical_symbols(self):
        """Test mathematical and scientific symbol entities."""
        html = '''
        <p>Math symbols: &alpha; &beta; &gamma; &delta;</p>
        <p>Operations: &plusmn; &times; &divide; &ne;</p>
        <p>Relations: &le; &ge; &asymp; &prop;</p>
        <p>Set theory: &sub; &sup; &cap; &cup;</p>
        <p>Logic: &and; &or; &not; &exist; &forall;</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode mathematical symbols
        assert "α" in markdown  # alpha
        assert "β" in markdown  # beta
        assert "±" in markdown  # plusmn
        assert "×" in markdown  # times
        assert "≠" in markdown  # ne
        assert "≤" in markdown  # le
        assert "⊂" in markdown  # sub
        assert "∧" in markdown  # and

    def test_currency_and_special_symbols(self):
        """Test currency and special symbol entities."""
        html = '''
        <p>Currencies: &euro; &pound; &yen; &cent;</p>
        <p>Arrows: &larr; &rarr; &uarr; &darr;</p>
        <p>Cards: &spades; &clubs; &hearts; &diams;</p>
        <p>Music: &sharp; &flat; &natural;</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode special symbols
        assert "€" in markdown  # euro
        assert "£" in markdown  # pound
        assert "¥" in markdown  # yen
        assert "←" in markdown  # larr
        assert "→" in markdown  # rarr
        assert "♠" in markdown  # spades
        assert "♥" in markdown  # hearts

    def test_entities_in_tables(self):
        """Test entities within table structures."""
        html = '''
        <table>
            <tr>
                <th>Symbol</th>
                <th>Entity</th>
                <th>Description</th>
            </tr>
            <tr>
                <td>&amp;</td>
                <td>&amp;amp;</td>
                <td>Ampersand &amp; conjunction</td>
            </tr>
            <tr>
                <td>&lt;</td>
                <td>&amp;lt;</td>
                <td>Less than &lt; symbol</td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode entities in table context
        assert "| Symbol | Entity | Description |" in markdown
        assert "| & |" in markdown
        assert "| < |" in markdown
        assert "Ampersand & conjunction" in markdown

    def test_entities_in_lists(self):
        """Test entities within list structures."""
        html = '''
        <ul>
            <li>Item with &amp; entity</li>
            <li>Mathematical: &alpha; + &beta; = &gamma;</li>
            <li>Code reference: Use &lt;tag&gt; for HTML</li>
        </ul>
        <ol>
            <li>First: &copy; copyright notice</li>
            <li>Second: &trade; trademark symbol</li>
        </ol>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode entities in list context
        assert "* Item with & entity" in markdown or "- Item with & entity" in markdown
        assert "α + β = γ" in markdown
        assert "Use <tag> for HTML" in markdown
        assert "1. First: © copyright" in markdown
        assert "2. Second: ™ trademark" in markdown

    def test_entities_in_blockquotes(self):
        """Test entities within blockquote structures."""
        html = '''
        <blockquote>
            <p>Quote with &ldquo;smart quotes&rdquo; and &amp; entity</p>
            <p>Mathematical quote: E = mc&sup2;</p>
            <cite>&mdash; Author &amp; Co.</cite>
        </blockquote>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should decode entities in blockquote context
        assert "> " in markdown
        assert "smart quotes" in markdown  # Content should be present
        assert "& entity" in markdown
        assert "mc" in markdown  # Superscript content should be present
        assert "Author & Co." in markdown

    def test_mixed_entity_types_in_paragraph(self):
        """Test paragraphs with mixed entity types."""
        html = '''
        <p>Mixed content: &amp; symbol, &#169; copyright, &#x2122; trademark,
        &quot;quoted text&quot; with &lt;tags&gt; and mathematical &alpha;&beta;&gamma; symbols.
        Punctuation: &hellip; and &mdash; dashes, plus currency &euro;100.</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle all entity types in one paragraph
        assert "& symbol" in markdown
        assert "© copyright" in markdown
        assert "™ trademark" in markdown
        assert '"quoted text"' in markdown
        assert "<tags>" in markdown
        assert "αβγ" in markdown
        assert "…" in markdown  # Ellipsis
        assert "—" in markdown  # Em dash
        assert "€100" in markdown

    def test_entities_with_surrounding_text(self):
        """Test entities with various surrounding text patterns."""
        html = '''
        <p>Start&amp;middle&amp;end</p>
        <p>Spaced &amp; entities &amp; here</p>
        <p>Mixed&nbsp;spacing &amp; patterns</p>
        <p>InWord&copy;Entity</p>
        <p>Multiple&hellip;&hellip;&hellip;dots</p>
        '''

        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle entities with different spacing
        assert "Start&middle&end" in markdown
        assert "Spaced & entities" in markdown
        assert "InWord" in markdown  # Copyright symbol should be present
        assert "Entity" in markdown
        assert "Multiple" in markdown and "dots" in markdown  # Ellipsis content

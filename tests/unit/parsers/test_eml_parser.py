#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_eml_ast.py
"""Unit tests for Email (EML) to AST converter.

Tests cover:
- Email header conversion
- Subject as H1 heading
- Email chain formatting
- Date formatting modes (iso8601, locale, strftime)
- Content preservation with HTMLInline
- Multiple message handling
- Thematic breaks between messages

"""

import datetime

import pytest

from all2md.ast import Document, Heading, HTMLInline, Paragraph, Text, ThematicBreak
from all2md.options import EmlOptions
from all2md.parsers.eml import EmlToAstConverter


def _create_test_email(**kwargs):
    """Create a test email dictionary.

    Parameters
    ----------
    **kwargs
        Email fields (from, to, subject, date, content, cc)

    Returns
    -------
    dict
        Email dictionary

    """
    return {
        "from": kwargs.get("from", "sender@example.com"),
        "to": kwargs.get("to", "recipient@example.com"),
        "subject": kwargs.get("subject", "Test Subject"),
        "date": kwargs.get("date", None),
        "content": kwargs.get("content", "Test content"),
        "cc": kwargs.get("cc", "")
    }


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic email conversion."""

    def test_single_email_minimal(self) -> None:
        """Test converting a single email with minimal content."""
        email = _create_test_email()
        converter = EmlToAstConverter()
        doc = converter.format_email_chain_as_ast([email])

        assert isinstance(doc, Document)
        # Should have: heading (subject), paragraph (headers), paragraph (content), thematic break
        assert len(doc.children) >= 3

    def test_subject_as_h1_enabled(self) -> None:
        """Test subject converted to H1 heading when enabled."""
        email = _create_test_email(subject="Important Email")
        options = EmlOptions(subject_as_h1=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # First child should be heading
        assert isinstance(doc.children[0], Heading)
        heading = doc.children[0]
        assert heading.level == 1
        assert isinstance(heading.content[0], Text)
        assert heading.content[0].content == "Important Email"

    def test_subject_as_h1_disabled(self) -> None:
        """Test subject not shown as H1 when disabled."""
        email = _create_test_email(subject="Important Email")
        options = EmlOptions(subject_as_h1=False, include_headers=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # First child should not be a H1 heading (should be paragraph with headers)
        if len(doc.children) > 0:
            first_child = doc.children[0]
            if isinstance(first_child, Heading):
                # If there is a heading, it shouldn't be our subject
                assert first_child.content[0].content != "Important Email"
            else:
                # Should be paragraph with headers including Subject
                assert isinstance(first_child, Paragraph)

    def test_include_headers_enabled(self) -> None:
        """Test email headers included when enabled."""
        email = _create_test_email(
            **{"from": "alice@example.com", "to": "bob@example.com"}
        )
        options = EmlOptions(include_headers=True, subject_as_h1=False)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Should have headers paragraph
        headers_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        text = content_item.content
                        if "From:" in text and "To:" in text:
                            headers_found = True
                            assert "alice@example.com" in text
                            assert "bob@example.com" in text
                            break
                if headers_found:
                    break

        assert headers_found, "Email headers not found in document"

    def test_include_headers_disabled(self) -> None:
        """Test email headers excluded when disabled."""
        email = _create_test_email()
        options = EmlOptions(include_headers=False, subject_as_h1=False)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Should not have headers paragraph (only content and separator)
        # Check that no "From:" or "To:" appear in text content
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        assert "From:" not in content_item.content

    def test_content_with_htmlinline(self) -> None:
        """Test email content preserved with Text nodes (not HTMLInline for security)."""
        email = _create_test_email(content="This is **markdown** content")
        options = EmlOptions(subject_as_h1=False, include_headers=False)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Should have content paragraph with Text (not HTMLInline for security)
        content_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        assert "markdown" in content_item.content
                        content_found = True
                        break
                if content_found:
                    break

        assert content_found, "Email content not found"


@pytest.mark.unit
class TestDateFormatting:
    """Tests for date formatting modes."""

    def test_date_format_iso8601(self) -> None:
        """Test date formatting in ISO8601 mode."""
        test_date = datetime.datetime(2025, 3, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
        email = _create_test_email(date=test_date)
        options = EmlOptions(
            include_headers=True,
            date_format_mode="iso8601"
        )
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Find headers paragraph and check date format
        date_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        if "Date:" in content_item.content:
                            # Should contain ISO8601 format
                            assert "2025-03-15" in content_item.content
                            date_found = True
                            break
                if date_found:
                    break

        assert date_found, "Date header not found"

    def test_date_format_strftime(self) -> None:
        """Test date formatting in strftime mode with custom pattern."""
        test_date = datetime.datetime(2025, 3, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
        email = _create_test_email(date=test_date)
        options = EmlOptions(
            include_headers=True,
            date_format_mode="strftime",
            date_strftime_pattern="%Y-%m-%d"
        )
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Find date in headers
        date_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        if "Date:" in content_item.content and "2025-03-15" in content_item.content:
                            date_found = True
                            break
                if date_found:
                    break

        assert date_found, "Formatted date not found"

    def test_date_none_handled(self) -> None:
        """Test that None date is handled gracefully."""
        email = _create_test_email(date=None)
        options = EmlOptions(include_headers=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Should not raise error, document should be created
        assert isinstance(doc, Document)


@pytest.mark.unit
class TestEmailChains:
    """Tests for multiple email handling."""

    def test_multiple_emails(self) -> None:
        """Test converting multiple emails in a chain."""
        emails = [
            _create_test_email(subject="Email 1", content="First message"),
            _create_test_email(subject="Email 2", content="Second message"),
            _create_test_email(subject="Email 3", content="Third message")
        ]

        options = EmlOptions(subject_as_h1=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast(emails)

        # Should have multiple headings (one per email)
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) == 3

        # Should have thematic breaks between emails
        breaks = [child for child in doc.children if isinstance(child, ThematicBreak)]
        assert len(breaks) == 3  # One after each email

    def test_thematic_breaks_between_emails(self) -> None:
        """Test that thematic breaks separate emails."""
        emails = [
            _create_test_email(content="Email 1"),
            _create_test_email(content="Email 2")
        ]

        converter = EmlToAstConverter()
        doc = converter.format_email_chain_as_ast(emails)

        # Check that ThematicBreaks exist
        breaks = [child for child in doc.children if isinstance(child, ThematicBreak)]
        assert len(breaks) >= 1

    def test_empty_email_list(self) -> None:
        """Test converting empty email list."""
        converter = EmlToAstConverter()
        doc = converter.format_email_chain_as_ast([])

        assert isinstance(doc, Document)
        assert len(doc.children) == 0


@pytest.mark.unit
class TestHeaderFields:
    """Tests for various header field handling."""

    def test_cc_field_included(self) -> None:
        """Test CC field included in headers."""
        email = _create_test_email(cc="cc@example.com")
        options = EmlOptions(include_headers=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Find CC in headers
        cc_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        if "cc:" in content_item.content and "cc@example.com" in content_item.content:
                            cc_found = True
                            break
                if cc_found:
                    break

        assert cc_found, "CC field not found in headers"

    def test_from_to_fields(self) -> None:
        """Test From and To fields in headers."""
        email = _create_test_email(
            **{"from": "sender@test.com", "to": "receiver@test.com"}
        )
        options = EmlOptions(include_headers=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Find From and To in headers
        from_found = False
        to_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        text = content_item.content
                        if "From:" in text and "sender@test.com" in text:
                            from_found = True
                        if "To:" in text and "receiver@test.com" in text:
                            to_found = True

        assert from_found, "From field not found"
        assert to_found, "To field not found"

    def test_subject_in_headers_when_not_h1(self) -> None:
        """Test subject appears in headers when subject_as_h1=False."""
        email = _create_test_email(subject="Test Subject")
        options = EmlOptions(include_headers=True, subject_as_h1=False)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Subject should appear in headers paragraph
        subject_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        if "Subject:" in content_item.content and "Test Subject" in content_item.content:
                            subject_found = True
                            break
                if subject_found:
                    break

        assert subject_found, "Subject not found in headers"

    def test_subject_not_in_headers_when_h1(self) -> None:
        """Test subject not duplicated in headers when subject_as_h1=True."""
        email = _create_test_email(subject="Test Subject")
        options = EmlOptions(include_headers=True, subject_as_h1=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Subject should not appear in headers paragraph (only as H1)
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        # Should not have "Subject:" line
                        assert "Subject:" not in content_item.content


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_content(self) -> None:
        """Test email with empty content."""
        email = _create_test_email(content="")
        converter = EmlToAstConverter()
        doc = converter.format_email_chain_as_ast([email])

        # Should still create document structure
        assert isinstance(doc, Document)
        # Should have separator at least
        assert len(doc.children) > 0

    def test_whitespace_only_content(self) -> None:
        """Test email with whitespace-only content."""
        email = _create_test_email(content="   \n\n   ")
        options = EmlOptions(subject_as_h1=False, include_headers=False)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Whitespace content should be skipped
        # Only separator should remain
        content_paragraphs = [child for child in doc.children if isinstance(child, Paragraph)]
        # Empty content should not create a paragraph
        for para in content_paragraphs:
            for content_item in para.content:
                if isinstance(content_item, HTMLInline):
                    # Content should be stripped
                    assert content_item.content.strip() == ""

    def test_special_characters_in_subject(self) -> None:
        """Test subject with special characters."""
        email = _create_test_email(subject="Re: Test [URGENT] <Important>")
        options = EmlOptions(subject_as_h1=True)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Subject should be preserved as-is
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.content[0].content == "Re: Test [URGENT] <Important>"

    def test_multiline_content(self) -> None:
        """Test email with multiline content."""
        content = "Line 1\nLine 2\nLine 3"
        email = _create_test_email(content=content)
        options = EmlOptions(subject_as_h1=False, include_headers=False)
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        # Content should be preserved as Text nodes (not HTMLInline for security)
        content_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for content_item in child.content:
                    if isinstance(content_item, Text):
                        assert "Line 1" in content_item.content
                        assert "Line 2" in content_item.content
                        assert "Line 3" in content_item.content
                        content_found = True
                        break
                if content_found:
                    break

        assert content_found, "Multiline content not preserved"


@pytest.mark.unit
class TestOptionsConfiguration:
    """Tests for EmlOptions configuration."""

    def test_default_options(self) -> None:
        """Test conversion with default options."""
        email = _create_test_email()
        converter = EmlToAstConverter()
        doc = converter.format_email_chain_as_ast([email])

        assert isinstance(doc, Document)
        # Default options should work without errors
        assert len(doc.children) > 0

    def test_all_options_enabled(self) -> None:
        """Test with all options enabled."""
        email = _create_test_email(
            subject="Test",
            date=datetime.datetime.now(datetime.timezone.utc),
            cc="cc@example.com"
        )
        options = EmlOptions(
            subject_as_h1=True,
            include_headers=True,
            date_format_mode="iso8601"
        )
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        assert isinstance(doc, Document)
        # Should have heading, headers paragraph, content, separator
        assert len(doc.children) >= 3

    def test_all_options_disabled(self) -> None:
        """Test with most options disabled."""
        email = _create_test_email()
        options = EmlOptions(
            subject_as_h1=False,
            include_headers=False
        )
        converter = EmlToAstConverter(options)
        doc = converter.format_email_chain_as_ast([email])

        assert isinstance(doc, Document)
        # Should have minimal output: content + separator
        assert len(doc.children) >= 1

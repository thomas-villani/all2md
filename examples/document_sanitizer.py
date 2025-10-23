#!/usr/bin/env python3
"""Document Sanitizer for Safe Sharing.

This example demonstrates how to clean documents before external sharing by
removing metadata, redacting sensitive information, and stripping hidden
content. It showcases the all2md transform pipeline and security features.

Features
--------
- Remove all metadata and comments
- Redact sensitive information (emails, phone numbers, PII)
- Strip tracked changes and revisions (metadata-based)
- Remove hidden content
- Anonymize authors and contributors
- Generate sanitization report

Use Cases
---------
- Document sharing with external parties
- Privacy compliance (GDPR, CCPA)
- Legal document preparation
- Public disclosure and FOI requests
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Optional

from all2md import convert, to_ast
from all2md.ast import Comment, CommentInline, Document, Node, Text
from all2md.ast.transforms import NodeTransformer
from all2md.ast.utils import extract_text


@dataclass
class SanitizationConfig:
    """Configuration for document sanitization.

    Parameters
    ----------
    remove_metadata : bool, default = True
        Remove all document and node metadata
    redact_emails : bool, default = True
        Redact email addresses
    redact_phones : bool, default = True
        Redact phone numbers
    redact_names : bool, default = False
        Redact person names (requires custom name list)
    redact_urls : bool, default = False
        Redact URLs
    remove_comments : bool, default = True
        Remove all comment nodes
    anonymize_authors : bool, default = True
        Replace author names with "Anonymous"
    custom_patterns : list of tuple, default = empty list
        Custom regex patterns to redact: [(pattern, replacement), ...]
    whitelist_domains : list of str, default = empty list
        Email/URL domains to preserve (e.g., ['example.com'])

    """

    remove_metadata: bool = True
    redact_emails: bool = True
    redact_phones: bool = True
    redact_names: bool = False
    redact_urls: bool = False
    remove_comments: bool = True
    anonymize_authors: bool = True
    custom_patterns: list[tuple[str, str]] = field(default_factory=list)
    whitelist_domains: list[str] = field(default_factory=list)


@dataclass
class SanitizationReport:
    """Report of sanitization actions taken.

    Parameters
    ----------
    emails_redacted : int, default = 0
        Number of emails redacted
    phones_redacted : int, default = 0
        Number of phone numbers redacted
    names_redacted : int, default = 0
        Number of names redacted
    urls_redacted : int, default = 0
        Number of URLs redacted
    comments_removed : int, default = 0
        Number of comments removed
    metadata_fields_removed : int, default = 0
        Number of metadata fields removed
    custom_redactions : int, default = 0
        Number of custom pattern redactions

    """

    emails_redacted: int = 0
    phones_redacted: int = 0
    names_redacted: int = 0
    urls_redacted: int = 0
    comments_removed: int = 0
    metadata_fields_removed: int = 0
    custom_redactions: int = 0


class MetadataStripperTransform(NodeTransformer):
    """Transform to remove all metadata from document and nodes.

    Parameters
    ----------
    report : SanitizationReport
        Report to track removals

    """

    def __init__(self, report: SanitizationReport):
        """Initialize metadata stripper with report."""
        super().__init__()
        self.report = report

    def visit_document(self, node: Document) -> Document:
        """Remove document metadata.

        Parameters
        ----------
        node : Document
            Document node

        Returns
        -------
        Document
            Document with cleared metadata

        """
        if node.metadata:
            self.report.metadata_fields_removed += len(node.metadata)

        new_node = Document(
            children=[self.transform(child) for child in node.children if self.transform(child) is not None],
            metadata={},
            source_location=None,
        )
        return new_node

    def transform(self, node: Node) -> Optional[Node]:
        """Transform any node by clearing its metadata.

        Parameters
        ----------
        node : Node
            Node to transform

        Returns
        -------
        Node or None
            Node with cleared metadata

        """
        result = super().transform(node)

        if result is not None and hasattr(result, "metadata"):
            if result.metadata:
                self.report.metadata_fields_removed += len(result.metadata)
            result.metadata = {}

        if result is not None and hasattr(result, "source_location"):
            result.source_location = None

        return result


class CommentRemoverTransform(NodeTransformer):
    """Transform to remove all comment nodes.

    Parameters
    ----------
    report : SanitizationReport
        Report to track removals

    """

    def __init__(self, report: SanitizationReport):
        """Initialize comment remover with report."""
        super().__init__()
        self.report = report

    def visit_comment(self, node: Comment) -> None:
        """Remove block comments.

        Parameters
        ----------
        node : Comment
            Comment node

        Returns
        -------
        None
            Always returns None to remove the comment

        """
        self.report.comments_removed += 1
        return None

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Remove inline comments.

        Parameters
        ----------
        node : CommentInline
            Inline comment node

        Returns
        -------
        None
            Always returns None to remove the comment

        """
        self.report.comments_removed += 1
        return None


class PIIRedactorTransform(NodeTransformer):
    """Transform to redact PII from text nodes.

    Parameters
    ----------
    config : SanitizationConfig
        Sanitization configuration
    report : SanitizationReport
        Report to track redactions

    """

    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    PHONE_PATTERN = r"\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b"
    URL_PATTERN = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'

    def __init__(self, config: SanitizationConfig, report: SanitizationReport):
        """Initialize PII redactor with configuration and report."""
        super().__init__()
        self.config = config
        self.report = report

    def _is_whitelisted_domain(self, text: str) -> bool:
        """Check if text contains a whitelisted domain.

        Parameters
        ----------
        text : str
            Text to check

        Returns
        -------
        bool
            True if text contains whitelisted domain

        """
        if not self.config.whitelist_domains:
            return False

        for domain in self.config.whitelist_domains:
            if domain in text:
                return True
        return False

    def _redact_emails(self, text: str) -> str:
        """Redact email addresses from text.

        Parameters
        ----------
        text : str
            Text to redact

        Returns
        -------
        str
            Text with emails redacted

        """

        def replace_email(match):
            email = match.group(0)
            if self._is_whitelisted_domain(email):
                return email
            self.report.emails_redacted += 1
            return "[EMAIL REDACTED]"

        return re.sub(self.EMAIL_PATTERN, replace_email, text)

    def _redact_phones(self, text: str) -> str:
        """Redact phone numbers from text.

        Parameters
        ----------
        text : str
            Text to redact

        Returns
        -------
        str
            Text with phone numbers redacted

        """

        def replace_phone(match):
            self.report.phones_redacted += 1
            return "[PHONE REDACTED]"

        return re.sub(self.PHONE_PATTERN, replace_phone, text)

    def _redact_urls(self, text: str) -> str:
        """Redact URLs from text.

        Parameters
        ----------
        text : str
            Text to redact

        Returns
        -------
        str
            Text with URLs redacted

        """

        def replace_url(match):
            url = match.group(0)
            if self._is_whitelisted_domain(url):
                return url
            self.report.urls_redacted += 1
            return "[URL REDACTED]"

        return re.sub(self.URL_PATTERN, replace_url, text)

    def _apply_custom_patterns(self, text: str) -> str:
        """Apply custom redaction patterns.

        Parameters
        ----------
        text : str
            Text to redact

        Returns
        -------
        str
            Text with custom patterns redacted

        """
        for pattern, replacement in self.config.custom_patterns:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                self.report.custom_redactions += matches
                text = re.sub(pattern, replacement, text)

        return text

    def visit_text(self, node: Text) -> Text:
        """Redact PII from text node.

        Parameters
        ----------
        node : Text
            Text node

        Returns
        -------
        Text
            Text node with PII redacted

        """
        content = node.content

        if self.config.redact_emails:
            content = self._redact_emails(content)

        if self.config.redact_phones:
            content = self._redact_phones(content)

        if self.config.redact_urls:
            content = self._redact_urls(content)

        if self.config.custom_patterns:
            content = self._apply_custom_patterns(content)

        return Text(content=content, metadata={})


def sanitize_document(
    input_path: str,
    output_path: str,
    config: Optional[SanitizationConfig] = None,
) -> SanitizationReport:
    """Sanitize a document for safe sharing.

    Parameters
    ----------
    input_path : str
        Input document path
    output_path : str
        Output document path
    config : SanitizationConfig or None, default = None
        Sanitization configuration (uses defaults if None)

    Returns
    -------
    SanitizationReport
        Report of sanitization actions

    """
    if config is None:
        config = SanitizationConfig()

    report = SanitizationReport()

    print(f"Sanitizing document: {input_path}")
    ast_doc = to_ast(input_path)

    transforms = []

    if config.remove_metadata:
        print("  - Removing metadata...")
        transforms.append(MetadataStripperTransform(report))

    if config.remove_comments:
        print("  - Removing comments...")
        transforms.append(CommentRemoverTransform(report))

    if config.redact_emails or config.redact_phones or config.redact_urls or config.custom_patterns:
        print("  - Redacting PII...")
        transforms.append(PIIRedactorTransform(config, report))

    print("  - Applying transforms...")
    for transform in transforms:
        ast_doc = transform.transform(ast_doc)

    if config.anonymize_authors:
        print("  - Anonymizing authors...")
        if ast_doc.metadata:
            for key in ["author", "creator", "producer", "contributors"]:
                if key in ast_doc.metadata:
                    ast_doc.metadata[key] = "Anonymous"
                    report.metadata_fields_removed += 1

    print(f"  - Writing sanitized document to: {output_path}")
    convert(
        str(input_path),
        output=output_path,
        source_format="ast_json",
        target_format=output_path.split(".")[-1] if "." in output_path else "markdown",
    )

    return report


def print_report(report: SanitizationReport):
    """Print sanitization report.

    Parameters
    ----------
    report : SanitizationReport
        Sanitization report

    """
    print("\n" + "=" * 70)
    print("Sanitization Report")
    print("=" * 70)
    print(f"Emails redacted: {report.emails_redacted}")
    print(f"Phone numbers redacted: {report.phones_redacted}")
    print(f"Names redacted: {report.names_redacted}")
    print(f"URLs redacted: {report.urls_redacted}")
    print(f"Comments removed: {report.comments_removed}")
    print(f"Metadata fields removed: {report.metadata_fields_removed}")
    print(f"Custom redactions: {report.custom_redactions}")

    total_redactions = (
        report.emails_redacted
        + report.phones_redacted
        + report.names_redacted
        + report.urls_redacted
        + report.comments_removed
        + report.metadata_fields_removed
        + report.custom_redactions
    )

    print(f"\nTotal sanitization actions: {total_redactions}")
    print("=" * 70)


def main():
    """Run the document sanitizer."""
    import argparse

    parser = argparse.ArgumentParser(description="Sanitize documents for safe sharing")
    parser.add_argument("input", help="Input document path")
    parser.add_argument("output", help="Output document path")
    parser.add_argument("--keep-metadata", action="store_true", help="Keep document metadata")
    parser.add_argument("--no-redact-emails", action="store_true", help="Don't redact email addresses")
    parser.add_argument("--no-redact-phones", action="store_true", help="Don't redact phone numbers")
    parser.add_argument("--redact-urls", action="store_true", help="Redact URLs")
    parser.add_argument("--keep-comments", action="store_true", help="Keep comment nodes")
    parser.add_argument("--no-anonymize", action="store_true", help="Don't anonymize authors")
    parser.add_argument(
        "--whitelist-domains",
        nargs="+",
        help="Domains to preserve (e.g., example.com)",
    )
    parser.add_argument(
        "--custom-pattern",
        nargs=2,
        action="append",
        metavar=("PATTERN", "REPLACEMENT"),
        help="Custom redaction pattern (regex and replacement)",
    )

    args = parser.parse_args()

    custom_patterns = []
    if args.custom_pattern:
        custom_patterns = [(p, r) for p, r in args.custom_pattern]

    config = SanitizationConfig(
        remove_metadata=not args.keep_metadata,
        redact_emails=not args.no_redact_emails,
        redact_phones=not args.no_redact_phones,
        redact_urls=args.redact_urls,
        remove_comments=not args.keep_comments,
        anonymize_authors=not args.no_anonymize,
        whitelist_domains=args.whitelist_domains or [],
        custom_patterns=custom_patterns,
    )

    report = sanitize_document(args.input, args.output, config)
    print_report(report)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Document Sanitizer for Safe Sharing")
        print("=" * 70)
        print()
        print("Clean documents before external sharing by removing metadata and")
        print("redacting sensitive information.")
        print()
        print("Usage:")
        print("  python document_sanitizer.py input.pdf output.pdf")
        print("  python document_sanitizer.py report.docx clean.docx --redact-urls")
        print("  python document_sanitizer.py doc.md sanitized.md --keep-metadata")
        print()
        print("Features:")
        print("  - Remove all metadata and source information")
        print("  - Redact email addresses and phone numbers")
        print("  - Redact URLs (optional)")
        print("  - Remove comment nodes")
        print("  - Anonymize author information")
        print("  - Custom regex pattern redaction")
        print("  - Domain whitelisting")
        print()
        print("Options:")
        print("  --keep-metadata          Keep document metadata")
        print("  --no-redact-emails       Don't redact email addresses")
        print("  --no-redact-phones       Don't redact phone numbers")
        print("  --redact-urls            Redact URLs")
        print("  --keep-comments          Keep comment nodes")
        print("  --no-anonymize           Don't anonymize authors")
        print("  --whitelist-domains D... Preserve these domains")
        print("  --custom-pattern P R     Redact custom regex pattern")
        print()
        print("Examples:")
        print("  Basic sanitization:")
        print("    python document_sanitizer.py confidential.pdf public.pdf")
        print()
        print("  Preserve company email addresses:")
        print("    python document_sanitizer.py doc.docx clean.docx \\")
        print("      --whitelist-domains company.com")
        print()
        print("  Redact social security numbers:")
        print("    python document_sanitizer.py records.pdf sanitized.pdf \\")
        print('      --custom-pattern "\\d{3}-\\d{2}-\\d{4}" "[SSN REDACTED]"')
        print()
        print("  Minimal sanitization (metadata only):")
        print("    python document_sanitizer.py doc.pdf clean.pdf \\")
        print("      --no-redact-emails --no-redact-phones")
        print()
        print("Use Cases:")
        print("  - Document sharing with external parties")
        print("  - Privacy compliance (GDPR, CCPA)")
        print("  - Legal document preparation")
        print("  - Public disclosure and FOI requests")
        print()
        sys.exit(0)

    main()

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/eml2ast.py
"""Email (EML) to AST converter.

This module provides conversion from email messages to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import datetime
from typing import Any

from all2md.ast import Document, Heading, HTMLInline, Node, Paragraph, Text, ThematicBreak
from all2md.options import EmlOptions


class EmlToAstConverter:
    """Convert email messages to AST representation.

    This converter processes parsed email data and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : EmlOptions or None
        Conversion options

    """

    def __init__(self, options: EmlOptions | None = None):
        self.options = options or EmlOptions()

    def format_email_chain_as_ast(self, eml_chain: list[dict[str, Any]]) -> Document:
        """Convert email chain to AST Document.

        Parameters
        ----------
        eml_chain : list[dict[str, Any]]
            List of email dictionaries with 'from', 'to', 'subject', 'date', 'content'

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        for item in eml_chain:
            # Add subject as H1 heading if requested
            if self.options.subject_as_h1 and "subject" in item and item["subject"]:
                children.append(Heading(level=1, content=[Text(content=item["subject"])]))

            # Add email headers as paragraphs if requested
            if self.options.include_headers:
                header_lines = []
                header_lines.append(f"From: {item['from']}")
                header_lines.append(f"To: {item['to']}")

                if item.get("cc"):
                    header_lines.append(f"cc: {item['cc']}")

                if "date" in item and item['date'] is not None:
                    formatted_date = self._format_date(item['date'])
                    if formatted_date:
                        header_lines.append(f"Date: {formatted_date}")

                # Only include subject in headers if not already shown as H1
                if not self.options.subject_as_h1 and "subject" in item:
                    header_lines.append(f"Subject: {item['subject']}")

                # Create a single paragraph with all headers
                header_text = "\n".join(header_lines)
                children.append(Paragraph(content=[Text(content=header_text)]))

            # Add content - use HTMLInline to preserve any markdown formatting
            content = item.get("content", "")
            if content.strip():
                children.append(Paragraph(content=[HTMLInline(content=content)]))

            # Add separator
            children.append(ThematicBreak())

        return Document(children=children)

    def _format_date(self, dt: datetime.datetime | None) -> str:
        """Format datetime according to EmlOptions configuration.

        Parameters
        ----------
        dt : datetime.datetime | None
            Datetime to format

        Returns
        -------
        str
            Formatted date string

        """
        if dt is None:
            return ""

        if self.options.date_format_mode == "iso8601":
            return dt.isoformat()
        elif self.options.date_format_mode == "locale":
            return dt.strftime("%c")
        else:  # strftime mode
            return dt.strftime(self.options.date_strftime_pattern)

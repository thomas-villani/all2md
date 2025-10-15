#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/flavors.py
"""Markdown flavor definitions and capabilities.

This module defines different markdown dialects/flavors and their capabilities.
Each flavor specifies which markdown features are supported, allowing the
renderer to adapt its output accordingly.

Supported Flavors
-----------------
- CommonMark: Strict CommonMark specification
- GFM (GitHub Flavored Markdown): CommonMark plus GitHub extensions
- MultiMarkdown: CommonMark plus MultiMarkdown extensions (footnotes, tables, etc.)
- Pandoc: Pandoc-flavored Markdown with extensive extensions
- Kramdown: Kramdown-flavored Markdown (Ruby Markdown processor)
- MarkdownPlus: All extensions enabled

"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MarkdownFlavor(ABC):
    """Abstract base class for markdown flavors.

    A flavor defines which markdown features are supported and how they
    should be rendered. Subclasses should implement capability checks
    for all extended features.

    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            Human-readable flavor name

        """
        pass

    @abstractmethod
    def supports_tables(self) -> bool:
        """Check if this flavor supports pipe tables.

        Returns
        -------
        bool
            True if pipe tables are supported

        """
        pass

    @abstractmethod
    def supports_task_lists(self) -> bool:
        """Check if this flavor supports task lists (checkboxes).

        Returns
        -------
        bool
            True if task lists are supported

        """
        pass

    @abstractmethod
    def supports_strikethrough(self) -> bool:
        """Check if this flavor supports strikethrough text.

        Returns
        -------
        bool
            True if strikethrough is supported

        """
        pass

    @abstractmethod
    def supports_autolinks(self) -> bool:
        """Check if this flavor supports automatic URL linking.

        Returns
        -------
        bool
            True if autolinks are supported

        """
        pass

    @abstractmethod
    def supports_footnotes(self) -> bool:
        """Check if this flavor supports footnotes.

        Returns
        -------
        bool
            True if footnotes are supported

        """
        pass

    @abstractmethod
    def supports_definition_lists(self) -> bool:
        """Check if this flavor supports definition lists.

        Returns
        -------
        bool
            True if definition lists are supported

        """
        pass

    @abstractmethod
    def supports_math(self) -> bool:
        """Check if this flavor supports math blocks.

        Returns
        -------
        bool
            True if math blocks are supported

        """
        pass


class CommonMarkFlavor(MarkdownFlavor):
    """Strict CommonMark specification flavor.

    This flavor adheres strictly to the CommonMark specification with no
    extensions. Features not in the spec are either rendered as HTML or
    ignored.

    References
    ----------
    CommonMark Spec: https://spec.commonmark.org/

    """

    @property
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            'CommonMark'

        """
        return "CommonMark"

    def supports_tables(self) -> bool:
        """Tables are not in CommonMark spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_task_lists(self) -> bool:
        """Task lists are not in CommonMark spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_strikethrough(self) -> bool:
        """Strikethrough is not in CommonMark spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_autolinks(self) -> bool:
        """CommonMark supports autolinks in angle brackets only.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_footnotes(self) -> bool:
        """Footnotes are not in CommonMark spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_definition_lists(self) -> bool:
        """Definition lists are not in CommonMark spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_math(self) -> bool:
        """Math blocks are not in CommonMark spec.

        Returns
        -------
        bool
            False

        """
        return False


class GFMFlavor(MarkdownFlavor):
    """GitHub Flavored Markdown (GFM) flavor.

    This flavor includes all CommonMark features plus GitHub extensions:
    - Pipe tables
    - Task lists
    - Strikethrough
    - Autolinks (extended)

    References
    ----------
    GFM Spec: https://github.github.com/gfm/

    """

    @property
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            'GFM'

        """
        return "GFM"

    def supports_tables(self) -> bool:
        """GFM supports pipe tables.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_task_lists(self) -> bool:
        """GFM supports task lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_strikethrough(self) -> bool:
        """GFM supports strikethrough with tildes.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_autolinks(self) -> bool:
        """GFM supports extended autolinks.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_footnotes(self) -> bool:
        """GFM does not support footnotes in the spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_definition_lists(self) -> bool:
        """GFM does not support definition lists.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_math(self) -> bool:
        """GFM supports math blocks with $$ delimiters.

        Returns
        -------
        bool
            True

        """
        return True


class MultiMarkdownFlavor(MarkdownFlavor):
    """MultiMarkdown flavor.

    This flavor implements the MultiMarkdown specification which extends
    CommonMark with:
    - Pipe tables
    - Footnotes
    - Definition lists
    - Math blocks
    - Citations
    - Abbreviations

    MultiMarkdown does not include task lists or autolinks by default.

    References
    ----------
    MultiMarkdown: https://fletcherpenney.net/multimarkdown/

    """

    @property
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            'MultiMarkdown'

        """
        return "MultiMarkdown"

    def supports_tables(self) -> bool:
        """MultiMarkdown supports pipe tables.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_task_lists(self) -> bool:
        """MultiMarkdown does not support task lists.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_strikethrough(self) -> bool:
        """MultiMarkdown does not support strikethrough in standard spec.

        Returns
        -------
        bool
            False

        """
        return False

    def supports_autolinks(self) -> bool:
        """MultiMarkdown supports basic autolinks (angle brackets).

        Returns
        -------
        bool
            True

        """
        return True

    def supports_footnotes(self) -> bool:
        """MultiMarkdown supports footnotes.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_definition_lists(self) -> bool:
        """MultiMarkdown supports definition lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_math(self) -> bool:
        """MultiMarkdown supports math blocks with LaTeX syntax.

        Returns
        -------
        bool
            True

        """
        return True


class PandocFlavor(MarkdownFlavor):
    """Pandoc Markdown flavor.

    This flavor implements Pandoc's extended Markdown syntax, which is
    one of the most feature-rich markdown dialects:
    - All GFM features (tables, strikethrough, task lists)
    - Footnotes
    - Definition lists
    - Math blocks (inline and display)
    - Superscript and subscript
    - Fenced divs
    - Attributes on elements
    - And many more extensions

    References
    ----------
    Pandoc Markdown: https://pandoc.org/MANUAL.html#pandocs-markdown

    """

    @property
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            'Pandoc'

        """
        return "Pandoc"

    def supports_tables(self) -> bool:
        """Pandoc supports multiple table formats.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_task_lists(self) -> bool:
        """Pandoc supports task lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_strikethrough(self) -> bool:
        """Pandoc supports strikethrough.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_autolinks(self) -> bool:
        """Pandoc supports autolinks.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_footnotes(self) -> bool:
        """Pandoc supports footnotes.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_definition_lists(self) -> bool:
        """Pandoc supports definition lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_math(self) -> bool:
        """Pandoc supports math with TeX syntax.

        Returns
        -------
        bool
            True

        """
        return True


class KramdownFlavor(MarkdownFlavor):
    """Kramdown Markdown flavor.

    This flavor implements Kramdown (Ruby Markdown processor) syntax:
    - All GFM features (tables, strikethrough, task lists)
    - Footnotes
    - Definition lists
    - Math blocks with $$ delimiters
    - Attributes on elements
    - Automatic ID generation for headers

    Kramdown is similar to GFM but adds footnotes and some other extensions.

    References
    ----------
    Kramdown: https://kramdown.gettalong.org/

    """

    @property
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            'Kramdown'

        """
        return "Kramdown"

    def supports_tables(self) -> bool:
        """Kramdown supports pipe tables.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_task_lists(self) -> bool:
        """Kramdown supports task lists (GFM-style).

        Returns
        -------
        bool
            True

        """
        return True

    def supports_strikethrough(self) -> bool:
        """Kramdown supports strikethrough.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_autolinks(self) -> bool:
        """Kramdown supports autolinks.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_footnotes(self) -> bool:
        """Kramdown supports footnotes.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_definition_lists(self) -> bool:
        """Kramdown supports definition lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_math(self) -> bool:
        """Kramdown supports math blocks with $$ delimiters.

        Returns
        -------
        bool
            True

        """
        return True


class MarkdownPlusFlavor(MarkdownFlavor):
    """Extended markdown flavor with all features enabled.

    This flavor supports all markdown extensions including:
    - All GFM features
    - Footnotes
    - Definition lists
    - Math blocks
    - And more

    This is the most permissive flavor, useful when maximum feature
    support is desired.

    """

    @property
    def name(self) -> str:
        """Get the flavor name.

        Returns
        -------
        str
            'MarkdownPlus'

        """
        return "MarkdownPlus"

    def supports_tables(self) -> bool:
        """MarkdownPlus supports tables.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_task_lists(self) -> bool:
        """MarkdownPlus supports task lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_strikethrough(self) -> bool:
        """MarkdownPlus supports strikethrough.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_autolinks(self) -> bool:
        """MarkdownPlus supports autolinks.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_footnotes(self) -> bool:
        """MarkdownPlus supports footnotes.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_definition_lists(self) -> bool:
        """MarkdownPlus supports definition lists.

        Returns
        -------
        bool
            True

        """
        return True

    def supports_math(self) -> bool:
        """MarkdownPlus supports math blocks.

        Returns
        -------
        bool
            True

        """
        return True

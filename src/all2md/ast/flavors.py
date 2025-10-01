#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/flavors.py
"""Markdown flavor definitions and capabilities.

This module defines different markdown dialects/flavors and their capabilities.
Each flavor specifies which markdown features are supported, allowing the
renderer to adapt its output accordingly.

Supported Flavors
-----------------
- CommonMark: Strict CommonMark specification
- GFM (GitHub Flavored Markdown): CommonMark plus GitHub extensions
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

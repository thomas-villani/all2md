#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_headers.py
"""PDF header identification utilities.

This private module contains the IdentifyHeaders class for analyzing
PDF font sizes and determining header levels.

"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Any

from all2md.options.pdf import PdfOptions

__all__ = ["IdentifyHeaders", "LineStyle", "SPACES", "compute_line_style"]

# Used to check relevance of text pieces
SPACES = set(string.whitespace)

# Mid-line sentence boundary: lowercase letter, then `.`/`!`/`?`, whitespace,
# then a capital letter. Catches multi-sentence body text while ignoring
# acronyms like "U.S. Department".
_INTERNAL_SENTENCE_BOUNDARY_RE = re.compile(r"[a-z][.!?]\s+[A-Z]")


class IdentifyHeaders:
    """Compute data for identifying header text based on font size analysis.

    This class analyzes font sizes across document pages to identify which
    font sizes should be treated as headers versus body text. It creates
    a mapping from font sizes to Markdown header levels (# ## ### etc.).

    Parameters
    ----------
    doc : fitz.Document
        PDF document to analyze
    pages : list[int], range, or None, optional
        Pages to analyze for font size distribution. If None, samples first 5 pages
        for performance on large PDFs.
    body_limit : float or None, optional
        Font size threshold below which text is considered body text.
        If None, uses the most frequent font size as body text baseline.
    options : PdfOptions or None, optional
        PDF conversion options containing header detection parameters.
        Use options.header_sample_pages to override the default sampling behavior.

    Attributes
    ----------
    header_id : dict[int, str]
        Mapping from font size to markdown header prefix string
    options : PdfOptions
        PDF conversion options used for header detection
    debug_info : dict or None
        Debug information about header detection (if header_debug_output is enabled).
        Contains font size distribution, header sizes, and classification details.

    """

    def __init__(
        self,
        doc: Any,  # PyMuPDF Document object
        pages: list[int] | range | None = None,
        body_limit: float | None = None,
        options: PdfOptions | None = None,
    ) -> None:
        """Initialize header identification by analyzing font sizes.

        Reads all text spans from specified pages and builds a frequency
        distribution of font sizes. Uses this to determine which font sizes
        should be treated as headers versus body text.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to analyze
        pages : list[int], range, or None, optional
            Pages to analyze for font size distribution. If None, samples first 5 pages.
        body_limit : float or None, optional
            Font size threshold below which text is considered body text.
            If None, uses the most frequent font size as body text baseline.
        options : PdfOptions or None, optional
            PDF conversion options containing header detection parameters.

        """
        self.options = options or PdfOptions()
        self.debug_info: dict[str, Any] | None = None
        self.header_id: dict[int, int] = {}
        self.bold_header_sizes: set[int] = set()
        self.allcaps_header_sizes: set[int] = set()

        # Step 1: Determine which pages to sample
        pages_to_use = self._determine_pages_to_sample(doc, pages)

        # Step 2: Collect font statistics from sampled pages
        fontsizes, fontweight_sizes, allcaps_sizes = self._collect_font_statistics(doc, pages_to_use)

        # Step 3: Apply filters (denylist, minimum occurrences)
        fontsizes = self._apply_filters(fontsizes)

        # Step 4: Determine body text size
        body_limit = self._determine_body_limit(fontsizes, body_limit)

        # Step 5: Calculate header sizes based on font size analysis
        sizes = self._calculate_header_sizes(fontsizes, body_limit)

        # Step 6: Add style-based headers (bold, all-caps)
        sizes = self._add_style_based_headers(sizes, fontweight_sizes, allcaps_sizes, body_limit, fontsizes)

        # Step 7: Build the header level mapping
        self._build_header_mapping(sizes)

        # Step 8: Store debug information if enabled
        self._store_debug_info(fontsizes, fontweight_sizes, allcaps_sizes, body_limit, sizes, pages_to_use)

    def _determine_pages_to_sample(
        self,
        doc: Any,
        pages: list[int] | range | None,
    ) -> list[int]:
        """Determine which pages to sample for header analysis.

        Parameters
        ----------
        doc : fitz.Document
            PDF document
        pages : list[int], range, or None
            User-specified pages to analyze

        Returns
        -------
        list[int]
            List of page indices to sample

        """
        if self.options.header_sample_pages is not None:
            if isinstance(self.options.header_sample_pages, int):
                return list(range(min(self.options.header_sample_pages, doc.page_count)))
            return [p for p in self.options.header_sample_pages if p < doc.page_count]

        if pages is not None:
            return pages if isinstance(pages, list) else list(pages)

        # Default: stratified sample so heading sizes that only appear past
        # the front matter (appendices, signature blocks, supplementary
        # sections) still get picked up.
        return self._stratified_sample_pages(doc.page_count)

    @staticmethod
    def _stratified_sample_pages(page_count: int, target: int = 12) -> list[int]:
        """Pick a representative sample of page indices for font analysis.

        For documents up to ``target`` pages, every page is sampled. Beyond
        that the sample is the union of:

            * the first 5 pages (front matter — title, TOC, intro)
            * the last 3 pages (signatures, references, version history)
            * a uniform interior stride filling the rest up to ``target``

        Returns sorted, deduplicated 0-based indices. Keeps the sample
        small (default 12 pages) so analysis stays cheap on long PDFs
        while no longer being blind to anything past page 5.
        """
        if page_count <= 0:
            return []
        if page_count <= target:
            return list(range(page_count))

        front = min(5, page_count)
        back = min(3, page_count)
        sampled: set[int] = set(range(front)) | set(range(page_count - back, page_count))

        remaining = max(0, target - len(sampled))
        if remaining > 0 and page_count > front + back:
            interior_start = front
            interior_end = page_count - back
            stride_count = remaining
            # Evenly space `stride_count` picks across the interior.
            for i in range(stride_count):
                idx = interior_start + (i + 1) * (interior_end - interior_start) // (stride_count + 1)
                sampled.add(idx)

        return sorted(sampled)

    def _collect_font_statistics(
        self,
        doc: Any,
        pages_to_use: list[int],
    ) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
        """Collect font size statistics from specified pages.

        Parameters
        ----------
        doc : fitz.Document
            PDF document
        pages_to_use : list[int]
            Page indices to analyze

        Returns
        -------
        tuple[dict[int, int], dict[int, int], dict[int, int]]
            Tuple of (fontsizes, fontweight_sizes, allcaps_sizes) dictionaries
            mapping font sizes to character counts

        """
        import fitz

        fontsizes: dict[int, int] = {}
        fontweight_sizes: dict[int, int] = {}
        allcaps_sizes: dict[int, int] = {}

        for pno in pages_to_use:
            page = doc[pno]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

            for span in self._iter_horizontal_spans(blocks):
                fontsz = round(span["size"])
                text = span["text"].strip()
                text_len = len(text)

                fontsizes[fontsz] = fontsizes.get(fontsz, 0) + text_len

                if self.options.header_use_font_weight and (span["flags"] & 16):
                    fontweight_sizes[fontsz] = fontweight_sizes.get(fontsz, 0) + text_len

                if self.options.header_use_all_caps and text.isupper() and text.isalpha():
                    allcaps_sizes[fontsz] = allcaps_sizes.get(fontsz, 0) + text_len

        return fontsizes, fontweight_sizes, allcaps_sizes

    @staticmethod
    def _iter_horizontal_spans(blocks: list) -> Any:
        """Yield non-empty horizontal text spans from blocks.

        Parameters
        ----------
        blocks : list
            Text blocks from PyMuPDF extraction

        Yields
        ------
        dict
            Text span dictionaries

        """
        for block in blocks:
            for line in block.get("lines", []):
                if line.get("dir") != (1, 0):
                    continue
                for span in line.get("spans", []):
                    if not SPACES.issuperset(span.get("text", "")):
                        yield span

    def _apply_filters(self, fontsizes: dict[int, int]) -> dict[int, int]:
        """Apply denylist and minimum occurrence filters to font sizes.

        Parameters
        ----------
        fontsizes : dict[int, int]
            Font size to character count mapping

        Returns
        -------
        dict[int, int]
            Filtered font size mapping

        """
        if self.options.header_size_denylist:
            for size in self.options.header_size_denylist:
                fontsizes.pop(round(size), None)

        if self.options.header_min_occurrences > 0:
            fontsizes = {k: v for k, v in fontsizes.items() if v >= self.options.header_min_occurrences}

        return fontsizes

    @staticmethod
    def _determine_body_limit(fontsizes: dict[int, int], body_limit: float | None) -> float:
        """Determine the body text font size.

        Parameters
        ----------
        fontsizes : dict[int, int]
            Font size to character count mapping
        body_limit : float or None
            User-specified body limit, or None to auto-detect

        Returns
        -------
        float
            Body text font size threshold

        """
        if body_limit is not None:
            return body_limit

        if not fontsizes:
            return 12.0

        # Choose the most frequent font size as body text
        most_frequent = max(fontsizes.items(), key=lambda x: x[1])
        return float(most_frequent[0])

    def _calculate_header_sizes(
        self,
        fontsizes: dict[int, int],
        body_limit: float,
    ) -> list[int]:
        """Calculate which font sizes should be treated as headers.

        Parameters
        ----------
        fontsizes : dict[int, int]
            Font size to character count mapping
        body_limit : float
            Body text font size threshold

        Returns
        -------
        list[int]
            Font sizes classified as headers, sorted descending

        """
        min_header_size = body_limit * self.options.header_font_size_ratio

        if self.options.header_percentile_threshold and fontsizes:
            sizes = self._calculate_by_percentile(fontsizes, min_header_size)
        else:
            sizes = sorted([f for f in fontsizes if f >= min_header_size], reverse=True)

        # Add sizes from allowlist
        if self.options.header_size_allowlist:
            for size in self.options.header_size_allowlist:
                rounded_size = round(size)
                if rounded_size not in sizes and rounded_size > body_limit:
                    sizes.append(rounded_size)
            sizes = sorted(sizes, reverse=True)

        return sizes

    def _calculate_by_percentile(
        self,
        fontsizes: dict[int, int],
        min_header_size: float,
    ) -> list[int]:
        """Calculate header sizes using percentile threshold.

        Parameters
        ----------
        fontsizes : dict[int, int]
            Font size to character count mapping
        min_header_size : float
            Minimum font size for headers

        Returns
        -------
        list[int]
            Font sizes meeting percentile and size thresholds

        """
        sorted_sizes = sorted(fontsizes.keys(), reverse=True)
        percentile_idx = int(len(sorted_sizes) * (1 - self.options.header_percentile_threshold / 100))

        if percentile_idx > 0:
            percentile_threshold = sorted_sizes[max(0, percentile_idx - 1)]
        else:
            percentile_threshold = sorted_sizes[0]

        return [s for s in sorted_sizes if s >= percentile_threshold and s >= min_header_size]

    def _add_style_based_headers(
        self,
        sizes: list[int],
        fontweight_sizes: dict[int, int],
        allcaps_sizes: dict[int, int],
        body_limit: float,
        size_totals: dict[int, int],
    ) -> list[int]:
        """Add bold and all-caps font sizes as potential headers.

        Two cases produce a style requirement:
            1. The size is admitted *only* because of bold/all-caps statistics
               (size alone wouldn't pass ``header_font_size_ratio``).
            2. The size also passes by size, but the vast majority of its
               characters are bold (or all-caps). This catches the common
               case where a size is shared between regular-weight body
               labels and bold subheadings — without a style requirement,
               the regular labels would be promoted as headings too.

        Parameters
        ----------
        sizes : list[int]
            Current list of header sizes
        fontweight_sizes : dict[int, int]
            Bold font size statistics
        allcaps_sizes : dict[int, int]
            All-caps font size statistics
        body_limit : float
            Body text font size threshold
        size_totals : dict[int, int]
            Total character count per size (for style-dominance ratios)

        Returns
        -------
        list[int]
            Updated header sizes including style-based headers

        """
        min_header_size = body_limit * self.options.header_font_size_ratio
        # Sizes within this multiple of body are "close to body" — they're
        # likely shared between body labels and bold subheadings, so we
        # demand a style hint to disambiguate. Sizes well above body
        # (>=1.2x) are confidently heading-like and qualify on size alone.
        ambiguous_size_ceiling = body_limit * 1.2

        if self.options.header_use_font_weight:
            # Case 1: size only passes via bold
            for size in fontweight_sizes:
                if size not in sizes and size >= min_header_size:
                    sizes.append(size)
                    self.bold_header_sizes.add(size)
            # Case 2: size passes by size but is close enough to body that
            # we can't tell heading from label without a style hint.
            for size in list(sizes):
                if size < ambiguous_size_ceiling:
                    self.bold_header_sizes.add(size)

        if self.options.header_use_all_caps:
            # Case 1: size only passes via all-caps
            for size in allcaps_sizes:
                if size not in sizes and size >= min_header_size:
                    sizes.append(size)
                    self.allcaps_header_sizes.add(size)
            # Case 2: size passes by size but is close to body and has
            # meaningful all-caps presence at that size — combine with the
            # bold check to allow EITHER style as a heading marker.
            for size in list(sizes):
                if size < ambiguous_size_ceiling and allcaps_sizes.get(size, 0) > 0:
                    self.allcaps_header_sizes.add(size)

        return sorted(set(sizes), reverse=True)

    def _build_header_mapping(self, sizes: list[int]) -> None:
        """Build the font size to header level mapping.

        Headings are ranked by descending size: the biggest size becomes h1,
        the next h2, and so on. There's one structural exception: if the
        document only ever surfaces a *single* heading size and that size
        requires bold styling, treat it as h2 rather than h1. Single-size
        heading documents in this shape are almost always "body + bold
        section heads" — not "body + display title". Reserving h1 for the
        layout-model TITLE (which would override via the layout path) keeps
        the heading hierarchy meaningful when an actual title appears.

        Parameters
        ----------
        sizes : list[int]
            Font sizes to map to header levels

        """
        single_style_restricted = len(sizes) == 1 and (
            sizes[0] in self.bold_header_sizes or sizes[0] in self.allcaps_header_sizes
        )
        for i, size in enumerate(sizes):
            level = min(i + 1, 6)  # Limit to h6
            if single_style_restricted:
                level = 2
            self.header_id[size] = level

    def _store_debug_info(
        self,
        fontsizes: dict[int, int],
        fontweight_sizes: dict[int, int],
        allcaps_sizes: dict[int, int],
        body_limit: float,
        sizes: list[int],
        pages_to_use: list[int],
    ) -> None:
        """Store debug information if enabled.

        Parameters
        ----------
        fontsizes : dict[int, int]
            Font size distribution
        fontweight_sizes : dict[int, int]
            Bold font size statistics
        allcaps_sizes : dict[int, int]
            All-caps font size statistics
        body_limit : float
            Body text font size
        sizes : list[int]
            Header font sizes
        pages_to_use : list[int]
            Pages that were sampled

        """
        if not self.options.header_debug_output:
            return

        self.debug_info = {
            "font_size_distribution": fontsizes.copy(),
            "bold_font_sizes": dict(fontweight_sizes),
            "allcaps_font_sizes": dict(allcaps_sizes),
            "body_text_size": body_limit,
            "header_sizes": list(sizes),
            "header_id_mapping": self.header_id.copy(),
            "bold_header_sizes": list(self.bold_header_sizes),
            "allcaps_header_sizes": list(self.allcaps_header_sizes),
            "percentile_threshold": self.options.header_percentile_threshold,
            "font_size_ratio": self.options.header_font_size_ratio,
            "min_occurrences": self.options.header_min_occurrences,
            "pages_sampled": list(pages_to_use),
        }

    def get_header_level(self, span: dict) -> int:
        """Return header level for a text span, or 0 if not a header.

        Backwards-compatible wrapper: extracts size, weight, and casing from a
        single span and delegates to :meth:`classify_line_style`. Most parser
        code paths should construct a ``LineStyle`` from all spans on a line
        and call :meth:`classify_line_style` directly so mixed-format lines
        classify correctly.
        """
        text = span.get("text", "").strip()
        is_bold = bool(span.get("flags", 0) & 16)
        is_allcaps = bool(text) and text.isupper() and any(c.isalpha() for c in text)
        return self.classify_line_style(
            size=round(span["size"]),
            text=text,
            is_bold=is_bold,
            is_allcaps=is_allcaps,
        )

    def classify_line_style(
        self,
        *,
        size: int,
        text: str,
        is_bold: bool,
        is_allcaps: bool,
    ) -> int:
        """Return header level for a line described by ``size``/``text``/style.

        Encapsulates the size lookup, style-requirement enforcement, and
        content validation in one place. The decoupled signature lets callers
        compute a single representative style across all spans on a line and
        avoid mis-classifying lines whose first span is whitespace, a glyph,
        or a numbering prefix that doesn't match the heading's font.
        """
        level = self.header_id.get(size, 0)
        if level <= 0:
            return 0

        # Sizes admitted only via bold/allcaps statistics must satisfy at
        # least one of those style requirements. A size with no entry in
        # either set is unconditional (size alone qualifies it).
        requires_bold = size in self.bold_header_sizes
        requires_allcaps = size in self.allcaps_header_sizes
        if requires_bold or requires_allcaps:
            satisfied = (requires_bold and is_bold) or (requires_allcaps and is_allcaps)
            if not satisfied:
                return 0

        # Content-based validation
        if not text:
            return 0
        if len(text) > self.options.header_max_line_length:
            return 0
        # Multi-sentence body text isn't a heading. Detected via lowercase
        # letter immediately preceding `.`/`!`/`?`, then whitespace, then a
        # capital letter — sidesteps acronyms like "U.S. Department".
        if _INTERNAL_SENTENCE_BOUNDARY_RE.search(text):
            return 0

        return level

    def get_debug_info(self) -> dict[str, Any] | None:
        """Return debug information about header detection.

        Returns
        -------
        dict or None
            Debug information dictionary if header_debug_output was enabled,
            None otherwise. The dictionary contains:
            - font_size_distribution: Frequency of each font size
            - bold_font_sizes: Sizes where bold text was found
            - allcaps_font_sizes: Sizes where all-caps text was found
            - body_text_size: Detected body text font size
            - header_sizes: Font sizes classified as headers
            - header_id_mapping: Mapping from size to header level
            - bold_header_sizes: Sizes treated as headers due to bold
            - allcaps_header_sizes: Sizes treated as headers due to all-caps
            - percentile_threshold: Threshold used for detection
            - font_size_ratio: Minimum ratio for header classification
            - min_occurrences: Minimum occurrences threshold
            - pages_sampled: Pages analyzed for header detection

        Examples
        --------
        >>> options = PdfOptions(header_debug_output=True)
        >>> hdr = IdentifyHeaders(doc, options=options)
        >>> debug_info = hdr.get_debug_info()
        >>> if debug_info:
        ...     print(f"Body text size: {debug_info['body_text_size']}")
        ...     print(f"Header sizes: {debug_info['header_sizes']}")

        """
        return self.debug_info


@dataclass(frozen=True)
class LineStyle:
    """Aggregate style of a PDF text line, derived from its non-whitespace spans.

    Carries the dominant font size (by character count), majority bold and
    all-caps flags, and the joined line text. Used by
    :meth:`IdentifyHeaders.classify_line_style` so heading classification
    sees the line as a whole rather than only its first span.
    """

    size: int
    text: str
    is_bold: bool
    is_allcaps: bool


def compute_line_style(spans: list[dict]) -> LineStyle | None:
    """Build a :class:`LineStyle` from a PyMuPDF line's spans.

    Returns ``None`` if the line has no non-whitespace text. The dominant
    integer size is the size with the most non-whitespace characters; bold
    and all-caps are decided by majority character count among non-empty
    text. Whitespace-only spans are skipped — they otherwise distort the
    "first span" view that classifiers used to rely on.
    """
    total_chars = 0
    size_chars: dict[int, int] = {}
    bold_chars = 0
    allcaps_chars = 0
    text_parts: list[str] = []

    for span in spans:
        raw_text = span.get("text", "")
        text_parts.append(raw_text)
        stripped = raw_text.strip()
        if not stripped:
            continue
        n = len(stripped)
        size = round(span.get("size", 0))
        size_chars[size] = size_chars.get(size, 0) + n
        total_chars += n
        if span.get("flags", 0) & 16:
            bold_chars += n
        if stripped.isupper() and any(c.isalpha() for c in stripped):
            allcaps_chars += n

    if total_chars == 0:
        return None

    dominant_size = max(size_chars.items(), key=lambda kv: kv[1])[0]
    line_text = "".join(text_parts).strip()

    return LineStyle(
        size=dominant_size,
        text=line_text,
        is_bold=(bold_chars * 2 >= total_chars),  # majority by char count
        is_allcaps=(allcaps_chars * 2 >= total_chars),
    )

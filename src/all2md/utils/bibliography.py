#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/bibliography.py
"""Bibliography utilities for footnote-to-citation conversion.

This module provides functions to:
1. Detect if footnote text is bibliographic
2. Parse bibliographic information from footnote text
3. Generate BibTeX entries from parsed data
4. Generate citation keys from author/title

The parsing is heuristic-based and handles common citation formats
including APA, MLA, Chicago, and informal academic citations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Patterns for detecting bibliographic content
_YEAR_PAREN_PATTERN = re.compile(r"\((\d{4})\)")  # (2023)
_YEAR_STANDALONE_PATTERN = re.compile(r"(?:^|[,;.\s])(\d{4})(?:[,;.\s]|$)")  # 2023.
_PAGE_PATTERN = re.compile(r"pp?\.?\s*(\d+(?:\s*[-–—]\s*\d+)?)", re.IGNORECASE)  # pp. 1-10
_VOLUME_PATTERN = re.compile(r"vol\.?\s*(\d+)", re.IGNORECASE)  # vol. 42
_DOI_PATTERN = re.compile(r"(?:doi:?\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,}/[^\s]+)", re.IGNORECASE)
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_AUTHOR_PATTERN = re.compile(r"([A-Z][a-z]+),\s+([A-Z]\.(?:\s*[A-Z]\.)*)")  # Smith, J. or Smith, J. K.
_ET_AL_PATTERN = re.compile(r"et\s+al\.?", re.IGNORECASE)  # et al.
_QUOTED_TITLE_PATTERN = re.compile(r'"([^"]{10,})"')  # "Title Here"
_ITALIC_TITLE_PATTERN = re.compile(r"\*([^*]{10,})\*")  # *Title Here*
_JOURNAL_INDICATORS = re.compile(
    r"\b(journal|proceedings|transactions|review|quarterly|annals|bulletin|letters)\b",
    re.IGNORECASE,
)

# BibTeX field escaping
_BIBTEX_SPECIAL_CHARS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


@dataclass
class ParsedReference:
    """Parsed bibliographic reference data.

    Parameters
    ----------
    authors : list of str
        Author names in "LastName, FirstName" format
    title : str
        Title of the work
    year : str or None
        Publication year
    journal : str or None
        Journal or book title
    volume : str or None
        Volume number
    issue : str or None
        Issue number
    pages : str or None
        Page range
    publisher : str or None
        Publisher name
    doi : str or None
        DOI identifier
    url : str or None
        URL if present
    entry_type : str
        BibTeX entry type (article, book, misc, etc.)
    raw_text : str
        Original source text
    confidence : float
        Confidence score from 0.0 to 1.0

    """

    authors: list[str] = field(default_factory=list)
    title: str = ""
    year: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    entry_type: str = "misc"
    raw_text: str = ""
    confidence: float = 0.0


def is_bibliographic_footnote(text: str) -> bool:
    """Detect if footnote text appears to be a bibliographic reference.

    Uses heuristics to identify common citation patterns:
    - Year in parentheses or standalone
    - Author name patterns (LastName, F.)
    - Page references (pp. X-Y)
    - DOI or URL presence
    - Journal/publication indicators

    Parameters
    ----------
    text : str
        Footnote text to analyze

    Returns
    -------
    bool
        True if text appears to be bibliographic

    Examples
    --------
    >>> is_bibliographic_footnote("Smith, J. (2023). Title. Journal, 42, 1-10.")
    True
    >>> is_bibliographic_footnote("See chapter 3 for more details.")
    False

    """
    if not text or len(text) < 20:
        return False

    score = 0

    # Check for year patterns (strong indicator)
    if _YEAR_PAREN_PATTERN.search(text):
        score += 2
    elif _YEAR_STANDALONE_PATTERN.search(text):
        score += 1

    # Check for author patterns
    if _AUTHOR_PATTERN.search(text):
        score += 2
    if _ET_AL_PATTERN.search(text):
        score += 1

    # Check for page references
    if _PAGE_PATTERN.search(text):
        score += 1

    # Check for volume
    if _VOLUME_PATTERN.search(text):
        score += 1

    # Check for DOI (very strong indicator)
    if _DOI_PATTERN.search(text):
        score += 3

    # Check for URL
    if _URL_PATTERN.search(text):
        score += 1

    # Check for quoted or italic title
    if _QUOTED_TITLE_PATTERN.search(text) or _ITALIC_TITLE_PATTERN.search(text):
        score += 1

    # Check for journal indicators
    if _JOURNAL_INDICATORS.search(text):
        score += 1

    # Threshold: need at least 3 points to be considered bibliographic
    return score >= 3


def parse_bibliographic_text(text: str) -> ParsedReference:
    """Parse bibliographic text into structured fields.

    Uses regex patterns to extract:
    - Authors (before year or first quoted string)
    - Title (quoted or italicized text)
    - Year (4-digit number)
    - Journal/Book (after title, before volume/pages)
    - Volume, Pages, DOI, URL

    Parameters
    ----------
    text : str
        Bibliographic text to parse

    Returns
    -------
    ParsedReference
        Structured reference data with confidence score

    Examples
    --------
    >>> ref = parse_bibliographic_text("Smith, J. (2023). A Study. Journal, 42, 1-10.")
    >>> ref.authors
    ['Smith, J.']
    >>> ref.year
    '2023'

    """
    ref = ParsedReference(raw_text=text)
    confidence_points = 0
    max_points = 10

    # Extract year
    year_match = _YEAR_PAREN_PATTERN.search(text)
    if year_match:
        ref.year = year_match.group(1)
        confidence_points += 2
    else:
        year_match = _YEAR_STANDALONE_PATTERN.search(text)
        if year_match:
            ref.year = year_match.group(1)
            confidence_points += 1

    # Extract DOI
    doi_match = _DOI_PATTERN.search(text)
    if doi_match:
        ref.doi = doi_match.group(1)
        confidence_points += 2

    # Extract URL (if no DOI)
    if not ref.doi:
        url_match = _URL_PATTERN.search(text)
        if url_match:
            ref.url = url_match.group(0)
            confidence_points += 1

    # Extract pages
    pages_match = _PAGE_PATTERN.search(text)
    if pages_match:
        ref.pages = pages_match.group(1).replace(" ", "")
        confidence_points += 1

    # Extract volume
    volume_match = _VOLUME_PATTERN.search(text)
    if volume_match:
        ref.volume = volume_match.group(1)
        confidence_points += 1

    # Extract authors (before year or title)
    authors = []
    for match in _AUTHOR_PATTERN.finditer(text):
        last_name = match.group(1)
        initials = match.group(2)
        authors.append(f"{last_name}, {initials}")
        if len(authors) >= 5:  # Limit to 5 authors
            break
    if authors:
        ref.authors = authors
        confidence_points += 2

    # Extract title (quoted or between year and journal)
    title_match = _QUOTED_TITLE_PATTERN.search(text)
    if title_match:
        ref.title = title_match.group(1).strip()
        confidence_points += 1
    else:
        italic_match = _ITALIC_TITLE_PATTERN.search(text)
        if italic_match:
            ref.title = italic_match.group(1).strip()
            confidence_points += 1
        elif ref.year:
            # Try to extract title after year
            year_pos = text.find(f"({ref.year})")
            if year_pos == -1:
                year_pos = text.find(ref.year)
            if year_pos != -1:
                after_year = text[year_pos + len(ref.year) + 2 :].strip()
                # Title is typically before the first period followed by a journal
                parts = after_year.split(".", 1)
                if parts and len(parts[0]) > 5:
                    ref.title = parts[0].strip()

    # Detect entry type
    if _JOURNAL_INDICATORS.search(text):
        ref.entry_type = "article"
    elif re.search(r"\bbook\b", text, re.IGNORECASE):
        ref.entry_type = "book"
    elif re.search(r"\b(conference|proceedings|workshop)\b", text, re.IGNORECASE):
        ref.entry_type = "inproceedings"
    elif re.search(r"\b(thesis|dissertation)\b", text, re.IGNORECASE):
        ref.entry_type = "phdthesis"
    else:
        ref.entry_type = "misc"

    ref.confidence = min(confidence_points / max_points, 1.0)
    return ref


def generate_citation_key(ref: ParsedReference, existing_keys: set[str] | None = None) -> str:
    """Generate a unique citation key from reference data.

    Format: AuthorYear (e.g., Smith2023)
    For multiple authors: SmithJones2023 or SmithEtAl2023

    Parameters
    ----------
    ref : ParsedReference
        Parsed reference data
    existing_keys : set of str, optional
        Set of existing keys to avoid collisions

    Returns
    -------
    str
        Unique citation key

    Examples
    --------
    >>> ref = ParsedReference(authors=["Smith, J."], year="2023")
    >>> generate_citation_key(ref)
    'Smith2023'

    """
    existing_keys = existing_keys or set()

    # Extract first author's last name
    if ref.authors:
        first_author = ref.authors[0]
        last_name = first_author.split(",")[0].strip()
        # Clean the last name
        last_name = re.sub(r"[^a-zA-Z]", "", last_name)
    else:
        # Fall back to first word of title
        if ref.title:
            last_name = ref.title.split()[0] if ref.title.split() else "Unknown"
            last_name = re.sub(r"[^a-zA-Z]", "", last_name)
        else:
            last_name = "Unknown"

    # Add year
    year = ref.year or "NoYear"

    # Create base key
    if len(ref.authors) == 2:
        second_author = ref.authors[1].split(",")[0].strip()
        second_author = re.sub(r"[^a-zA-Z]", "", second_author)
        base_key = f"{last_name}{second_author}{year}"
    elif len(ref.authors) > 2:
        base_key = f"{last_name}EtAl{year}"
    else:
        base_key = f"{last_name}{year}"

    # Ensure uniqueness
    key = base_key
    counter = 1
    while key in existing_keys:
        counter += 1
        key = f"{base_key}{chr(ord('a') + counter - 2)}"  # Smith2023a, Smith2023b, etc.

    return key


def escape_bibtex_value(value: str) -> str:
    """Escape special characters for BibTeX.

    Parameters
    ----------
    value : str
        Value to escape

    Returns
    -------
    str
        Escaped value safe for BibTeX

    """
    result = value
    for char, escaped in _BIBTEX_SPECIAL_CHARS.items():
        result = result.replace(char, escaped)
    return result


def generate_bibtex_entry(key: str, ref: ParsedReference) -> str:
    """Generate BibTeX entry string from parsed reference.

    Parameters
    ----------
    key : str
        Citation key
    ref : ParsedReference
        Parsed reference data

    Returns
    -------
    str
        Complete BibTeX entry

    Examples
    --------
    >>> ref = ParsedReference(
    ...     authors=["Smith, J."],
    ...     title="A Study",
    ...     year="2023",
    ...     journal="Journal of Examples",
    ...     entry_type="article"
    ... )
    >>> print(generate_bibtex_entry("Smith2023", ref))
    @article{Smith2023,
      author = {Smith, J.},
      title = {A Study},
      journal = {Journal of Examples},
      year = {2023}
    }

    """
    lines = [f"@{ref.entry_type}{{{key},"]

    # Author
    if ref.authors:
        author_str = " and ".join(ref.authors)
        lines.append(f"  author = {{{escape_bibtex_value(author_str)}}},")

    # Title
    if ref.title:
        lines.append(f"  title = {{{escape_bibtex_value(ref.title)}}},")

    # Journal/booktitle
    if ref.journal:
        if ref.entry_type == "inproceedings":
            lines.append(f"  booktitle = {{{escape_bibtex_value(ref.journal)}}},")
        else:
            lines.append(f"  journal = {{{escape_bibtex_value(ref.journal)}}},")

    # Year
    if ref.year:
        lines.append(f"  year = {{{ref.year}}},")

    # Volume
    if ref.volume:
        lines.append(f"  volume = {{{ref.volume}}},")

    # Issue/number
    if ref.issue:
        lines.append(f"  number = {{{ref.issue}}},")

    # Pages
    if ref.pages:
        lines.append(f"  pages = {{{ref.pages}}},")

    # Publisher
    if ref.publisher:
        lines.append(f"  publisher = {{{escape_bibtex_value(ref.publisher)}}},")

    # DOI
    if ref.doi:
        lines.append(f"  doi = {{{ref.doi}}},")

    # URL
    if ref.url:
        lines.append(f"  url = {{{ref.url}}},")

    # Note with raw text (truncated)
    if ref.raw_text and len(ref.raw_text) <= 200:
        # Only include if relatively short
        clean_text = ref.raw_text.replace("\n", " ").strip()
        lines.append(f"  note = {{Original: {escape_bibtex_value(clean_text)}}},")

    # Remove trailing comma from last field
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]

    lines.append("}")
    return "\n".join(lines)


def generate_bibtex_file(entries: list[tuple[str, ParsedReference]]) -> str:
    """Generate complete BibTeX file content from multiple entries.

    Parameters
    ----------
    entries : list of (key, ParsedReference) tuples
        Citation keys and their parsed references

    Returns
    -------
    str
        Complete BibTeX file content

    """
    parts = []
    for key, ref in entries:
        parts.append(generate_bibtex_entry(key, ref))

    return "\n\n".join(parts)

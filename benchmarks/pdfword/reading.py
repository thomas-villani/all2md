"""One document as Word reads it: the shape shared by the truth record and every conversion.

No COM here, so truth records load and scoring runs anywhere. `benchmarks.pdfword.word` fills
these in on Windows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Paragraph:
    """A paragraph outside any table.

    ``level`` is 0 for the Title style, 1-9 for an outline level, and None for body text.
    ``marker`` is the label Word prints from its own numbering (None when the paragraph is
    not a Word list item, even if its text starts with a typed "1.1").
    """

    text: str
    style: str = "Normal"
    level: int | None = None
    marker: str | None = None
    list_level: int | None = None


@dataclass(frozen=True)
class Table:
    """A table's cell text, row by row. Vertically merged cells take the row Word reports."""

    rows: tuple[tuple[str, ...], ...]

    @property
    def shape(self) -> tuple[int, int]:
        """Return (rows, widest row)."""
        return len(self.rows), max((len(row) for row in self.rows), default=0)


Block = Paragraph | Table


@dataclass(frozen=True)
class Reading:
    """Everything the lane compares about one document."""

    blocks: tuple[Block, ...]
    footnotes: tuple[str, ...] = ()
    headers: tuple[str, ...] = ()
    footers: tuple[str, ...] = ()
    pictures: int = 0
    pages: int = 0
    page_width: float = 0.0
    page_height: float = 0.0
    margins: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # top, bottom, left, right
    columns: int = 1
    body_font: str = ""
    body_size: float = 0.0
    #: Words inside text boxes or frames. They look right and are awkward to edit.
    float_words: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def paragraphs(self) -> tuple[Paragraph, ...]:
        """Return the paragraphs, without the tables."""
        return tuple(block for block in self.blocks if isinstance(block, Paragraph))

    @property
    def tables(self) -> tuple[Table, ...]:
        """Return the tables, without the paragraphs."""
        return tuple(block for block in self.blocks if isinstance(block, Table))

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-ready dict."""
        data = asdict(self)
        data["blocks"] = [
            {"table": [list(row) for row in block.rows]} if isinstance(block, Table) else asdict(block)
            for block in self.blocks
        ]
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Reading:
        """Rebuild a reading from :meth:`to_json`'s output."""
        blocks: list[Block] = []
        for block in data["blocks"]:
            if "table" in block:
                blocks.append(Table(rows=tuple(tuple(row) for row in block["table"])))
            else:
                blocks.append(Paragraph(**block))
        values = {key: value for key, value in data.items() if key != "blocks"}
        for key in ("footnotes", "headers", "footers", "margins"):
            values[key] = tuple(values[key])
        return cls(blocks=tuple(blocks), **values)

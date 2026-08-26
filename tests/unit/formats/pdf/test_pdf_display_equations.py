#  Copyright (c) 2025 Tom Villani, Ph.D.
"""A display equation's variables are not emphasised text (#456).

An equation is typeset glyph by glyph: each variable, operator and bracket piece
is its own span in its own font. An italic variable is italic *because it is a
variable*, so wrapping each one separately turns an equation into
``*e* *c* *e* *S* *m* *R*`` -- markup asserting that a dozen single letters are
each stressed, which is neither what the page means nor anything a reader or a
model can use.

Two tests decide, and both must hold, because either alone claims real prose.
The line must carry math evidence -- a substantial share of its spans in a math
font, or a Private Use codepoint anywhere in it -- and it must be short. Prose
reaches for a Greek letter often enough ("in terms of electronic density rho,
momentum p") that evidence alone would strip 36 sentences on the corpus that are
merely *about* mathematics.

Evidence is not spread evenly down an equation, which is why the block test
exists: one line carries the operators in a symbol font, the next carries only
the variables in the ordinary text italic and is indistinguishable from prose by
itself. Its neighbours are what identify it.

The font names and codepoints here are the real ones, from PMC3000079.1 and
PMC5000011.1 in the dev corpus.
"""

import pytest

from all2md.parsers._pdf_math import is_equation_block, is_equation_line, mark_equation_blocks

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

ITALIC = 2  # PyMuPDF's italic flag


def _span(text: str, font: str = "TimesNewRoman", *, italic: bool = False) -> dict:
    return {"text": text, "font": font, "flags": ITALIC if italic else 0}


def _line(*spans: dict) -> dict:
    return {"spans": list(spans)}


class TestALineOfAnEquation:
    def test_symbol_font_operators_are_an_equation(self) -> None:
        """``\uf0b6`` is Symbol's partial-derivative sign, addressed through the PUA."""
        spans = [_span("\uf0b6", "Symbol"), _span("\uf02b", "Symbol"), _span("\uf03d", "Symbol")]

        assert is_equation_line(spans)

    def test_a_math_font_without_private_use_is_an_equation(self) -> None:
        """TeX's math italic carries ordinary codepoints; the font name is the evidence."""
        spans = [_span("x", "CMMI10", italic=True), _span("=", "CMSY10"), _span("y", "CMMI10", italic=True)]

        assert is_equation_line(spans)

    def test_prose_naming_a_greek_letter_is_not_an_equation(self) -> None:
        """The measured false positive: 36 corpus lines of 11-24 words carry a symbol span.

        "in terms of electronic density rho, momentum p, total energy E" is a
        sentence about mathematics, and its one Greek letter must not cost it its
        typography.
        """
        spans = [
            _span("in terms of electronic density "),
            _span("\uf072", "Symbol"),
            _span(", momentum p, total energy E and the chemical field"),
        ]

        assert not is_equation_line(spans)

    def test_a_short_italic_line_without_math_evidence_is_not_an_equation(self) -> None:
        """Shortness alone is worthless -- a page is full of short italic lines."""
        spans = [_span("Int. J. Mol. Sci.", "TimesNewRoman-Italic", italic=True)]

        assert not is_equation_line(spans)

    def test_no_spans_is_not_an_equation(self) -> None:
        assert not is_equation_line([])


class TestABlockOfAnEquation:
    def test_variables_inherit_evidence_from_their_neighbours(self) -> None:
        """The line the per-line test cannot reach.

        The second line here is variables in the text italic and nothing else --
        prose by every signal it carries alone. The operators above it say what
        it is.
        """
        block = {
            "lines": [
                _line(_span("\uf0e6", "Symbol"), _span("\uf0b6", "Symbol"), _span("\uf03d", "Symbol")),
                _line(_span("x", italic=True), _span("t", italic=True), _span("S", italic=True)),
            ]
        }

        assert is_equation_block(block)

    def test_a_paragraph_quoting_one_formula_is_not_an_equation_block(self) -> None:
        """A block long enough to be prose keeps its typography, whatever it quotes."""
        prose = "The bondon mass is recovered from the relation above and compared against "
        block = {
            "lines": [
                _line(_span(prose), _span("\uf0b6", "Symbol")),
                _line(_span("the experimental values reported for the same series of compounds")),
            ]
        }

        assert not is_equation_block(block)

    def test_one_evidence_line_among_many_does_not_carry_the_block(self) -> None:
        """Half the lines must agree, so a single symbol span cannot claim the rest."""
        block = {
            "lines": [
                _line(_span("\uf0b6", "Symbol")),
                _line(_span("first", italic=True)),
                _line(_span("second", italic=True)),
                _line(_span("third", italic=True)),
            ]
        }

        assert not is_equation_block(block)

    def test_an_empty_block_is_not_an_equation(self) -> None:
        assert not is_equation_block({"lines": []})
        assert not is_equation_block({})


def _eq_block(bbox: tuple[float, float, float, float]) -> dict:
    """A block that carries its own evidence: symbol-font operators over italic variables."""
    return {
        "bbox": bbox,
        "lines": [
            _line(_span("\uf0e6", "Symbol"), _span("\uf0b6", "Symbol"), _span("\uf03d", "Symbol")),
            _line(_span("x", italic=True), _span("t", italic=True)),
        ],
    }


def _glyph_run(bbox: tuple[float, float, float, float], *glyphs: str) -> dict:
    """A block of loose glyphs, one to a line, carrying no evidence of its own."""
    return {"bbox": bbox, "lines": [_line(_span(glyph, italic=True)) for glyph in glyphs]}


def _prose_block(bbox: tuple[float, float, float, float], text: str) -> dict:
    return {"bbox": bbox, "lines": [_line(_span(text))]}


class TestAnEquationSpreadOverSeveralBlocks:
    """PyMuPDF splits an equation wherever its glyphs stop lining up (#456).

    The operators land in one block and the variables in the next, so a block that
    is plainly part of an equation on the page can carry no evidence at all on its
    own. What identifies it is the block printed against it.
    """

    def test_a_glyph_run_against_an_equation_joins_it(self) -> None:
        blocks = [_eq_block((100, 100, 300, 120)), _glyph_run((100, 121, 300, 160), "S", "R", "c", "e")]

        assert mark_equation_blocks(blocks) == [True, True]

    def test_the_seed_spreads_transitively_along_the_run(self) -> None:
        """An equation reaches its far side one block at a time."""
        blocks = [
            _eq_block((100, 100, 300, 120)),
            _glyph_run((100, 121, 300, 140), "S", "R"),
            _glyph_run((100, 141, 300, 160), "c", "e"),
        ]

        assert mark_equation_blocks(blocks) == [True, True, True]

    def test_spreading_stops_at_the_first_block_that_reads_as_text(self) -> None:
        blocks = [
            _eq_block((100, 100, 300, 120)),
            _prose_block((100, 121, 300, 135), "that can be rearranged as follows"),
            _glyph_run((100, 136, 300, 160), "S", "R"),
        ]

        assert mark_equation_blocks(blocks) == [True, False, False]

    def test_a_glyph_run_far_from_the_equation_is_left_alone(self) -> None:
        """Two pieces of one equation are printed touching; a running head is not.

        A journal's running head is set one glyph to a line by the same shredding
        that produces the equation fragments, so without the distance test it joins
        the first equation on the page.
        """
        blocks = [_eq_block((100, 400, 300, 420)), _glyph_run((100, 60, 300, 90), "Int.", "J.", "Mol.")]

        assert mark_equation_blocks(blocks) == [True, False]

    def test_a_glyph_run_with_no_equation_near_it_stays_prose(self) -> None:
        """The signature alone is not enough, and this is why.

        A table's data row is also more printed lines than words -- one article in
        the dev corpus offers eighty of them. Only contiguity with a real equation
        tells the two apart, so on a page without one nothing is admitted.
        """
        row = _glyph_run((100, 100, 300, 140), "Female", "1,060", "(47.77)", "0.02", "0.20")
        blocks = [row, _glyph_run((100, 141, 300, 180), "Male", "1,159", "(52.23)", "0.04", "0.06")]

        assert mark_equation_blocks(blocks) == [False, False]

    def test_a_block_of_real_words_is_never_a_glyph_run(self) -> None:
        """More words than printed lines is text, however short it is."""
        blocks = [
            _eq_block((100, 100, 300, 120)),
            {
                "bbox": (100, 121, 300, 140),
                "lines": [_line(_span("since calling the relations abstracted from"))],
            },
        ]

        assert mark_equation_blocks(blocks) == [True, False]

    def test_a_page_with_no_equations_marks_nothing(self) -> None:
        blocks = [_prose_block((100, 100, 300, 120), "An ordinary paragraph of running text.")]

        assert mark_equation_blocks(blocks) == [False]

    def test_no_blocks_marks_nothing(self) -> None:
        assert mark_equation_blocks([]) == []

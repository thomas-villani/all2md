"""Which ``w:numFmt`` values count as an ordered list.

ECMA-376 ST_NumberFormat enumerates some sixty numbering schemes and only two of
them are not a counter, so the mapping tests for the exceptions rather than
carrying a list of knowns. The parser used to recognise five Western values and
silently demote the other forty-one -- almost entirely CJK, Hebrew and Arabic --
to bullets.
"""

import pytest

from all2md.parsers.docx import _map_numbering_format

pytestmark = [pytest.mark.unit, pytest.mark.docx]

# A spread of what Word actually writes, measured against Word 16.0.20326 and
# recorded in benchmarks/docx/generate/numfmt-map.json (46 distinct values).
ORDERED_FORMATS = [
    "decimal",
    "lowerLetter",
    "upperLetter",
    "lowerRoman",
    "upperRoman",
    "decimalZero",
    "decimalEnclosedCircle",
    "decimalEnclosedFullstop",
    "decimalEnclosedParen",
    "decimalFullWidth",
    "decimalHalfWidth",
    "ordinal",
    "ordinalText",
    "cardinalText",
    "chicago",
    "hex",
    "arabicAlpha",
    "hebrew1",
    "hebrew2",
    "aiueo",
    "iroha",
    "chineseCounting",
    "chineseLegalSimplified",
    "japaneseCounting",
    "japaneseLegal",
    "koreanCounting",
    "koreanLegal",
    "taiwaneseCounting",
    "ideographTraditional",
    "ideographZodiac",
    "ganada",
    "chosung",
]


@pytest.mark.parametrize("fmt", ORDERED_FORMATS)
def test_every_counting_scheme_is_an_ordered_list(fmt):
    assert _map_numbering_format(fmt) == "number"


@pytest.mark.parametrize("fmt", ["bullet", "none"])
def test_the_two_uncounted_schemes_are_bullets(fmt):
    assert _map_numbering_format(fmt) == "bullet"


def test_a_custom_scheme_still_counts():
    # w:numFmt val="custom" defers the glyph to w:numFmtCustom, but the item is
    # still numbered.
    assert _map_numbering_format("custom") == "number"


def test_an_unrecognised_value_counts_rather_than_disappearing():
    # Guessing "ordered" is the safe direction: a value we have never seen is far
    # more likely to be a counting scheme than one of the two that are not.
    assert _map_numbering_format("somethingWordNeverWrites") == "number"


@pytest.mark.parametrize("fmt", [None, ""])
def test_no_format_at_all_maps_to_nothing(fmt):
    assert _map_numbering_format(fmt) is None

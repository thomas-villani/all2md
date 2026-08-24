"""Behavioral tests for direct annotation and AST fidelity projections."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from all2md.ast.nodes import (
    CodeBlock,
    Comment,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    Figure,
    Heading,
    Image,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from benchmarks.omnidocbench import oracles
from benchmarks.omnidocbench.oracles import (
    FormulaProjection,
    PageProjection,
    TableProjection,
    content_similarity,
    project_annotation,
    project_ast,
    score_page,
)

pytestmark = pytest.mark.unit


def test_annotation_projection_uses_order_and_supported_ground_truth() -> None:
    """External facts must come from annotation fields, not from an all2md renderer."""
    record = {
        "page_info": {"image_path": "nested/page-7.jpg", "page_attribute": {"data_source": "testsource"}},
        "layout_dets": [
            {
                "category_type": "text_block",
                "order": 3,
                "text": "Body",
                "ignore": False,
                "line_with_spans": [
                    {"category_type": "text_span", "text": "Body"},
                    {"category_type": "equation_inline", "latex": "$a$"},
                    {"category_type": "equation_inline", "latex": "$ignored$", "ignore": True},
                ],
            },
            {"category_type": "code_txt", "order": 2, "text": "print(1)", "ignore": False},
            {
                "category_type": "table",
                "order": 4,
                "html": "<table><tr><th colspan='2'>Head</th></tr><tr><td>A</td><td>B</td></tr></table>",
                "ignore": False,
            },
            {"category_type": "title", "order": 1, "text": "Title", "ignore": False},
            {
                "category_type": "equation_isolated",
                "order": 5,
                "latex": "$$x + y$$",
                "ignore": False,
            },
            {
                "category_type": "figure",
                "order": 6,
                "ignore": False,
                "line_with_spans": [{"category_type": "equation_inline", "latex": "$b$"}],
            },
            {"category_type": "footer", "order": 7, "ignore": True},
        ],
    }

    truth = project_annotation(record)

    assert truth.page_id == "page-7"
    assert truth.projection.text_blocks == ("Title", "print(1)", "Body", "Head A B")
    assert truth.projection.block_kinds == (
        "title",
        "text_block",
        "text_block",
        "table",
        "equation_isolated",
    )
    assert truth.projection.tables == (TableProjection(2, 2, 4, "Head A B"),)
    assert truth.projection.formulas == (
        FormulaProjection("inline", "$a$"),
        FormulaProjection("block", "$$x + y$$"),
        FormulaProjection("inline", "$b$"),
    )
    assert truth.unscored_categories == {"figure": 1}
    assert truth.explicitly_ignored == 2


def test_ast_projection_reads_nodes_directly_in_document_order() -> None:
    """Scoring must inspect one AST and preserve its semantic block order."""
    table = Table(
        header=TableRow(cells=[TableCell(content=[Text(content="Head")], colspan=2)]),
        rows=[
            TableRow(
                cells=[
                    TableCell(content=[Text(content="A")]),
                    TableCell(content=[Text(content="B")]),
                ]
            )
        ],
    )
    document = Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            CodeBlock(content="print(1)"),
            Paragraph(
                content=[
                    Text(content="Body"),
                    MathInline(
                        content="<math>a</math>",
                        notation="mathml",
                        representations={"latex": "a"},
                    ),
                ]
            ),
            table,
            MathBlock(
                content="<math>x + y</math>",
                notation="mathml",
                representations={"latex": "x + y"},
            ),
        ]
    )

    projection = project_ast(document)

    assert projection.text_blocks == ("Title", "print(1)", "Body <math>a</math>", "Head A B")
    assert projection.block_kinds == (
        "title",
        "text_block",
        "text_block",
        "table",
        "equation_isolated",
    )
    assert projection.tables == (TableProjection(2, 2, 4, "Head A B"),)
    assert projection.formulas == (
        FormulaProjection("inline", "a"),
        FormulaProjection("block", "x + y"),
    )


def test_bound_captions_are_projected_text_not_invisible_attributes() -> None:
    """A caption bound to a Figure, Table, or Image must count as page text (#406).

    The annotation side has always collapsed ``figure_caption``/``table_caption`` to
    ``text_block``; the AST side used to descend children only, so a caption the parser
    correctly folded into a ``caption`` attribute vanished from measurement -- recall fell
    as figure binding improved. 101 of the 103 "lost" captions on the held-out PMC corpus
    were in the output the whole time.
    """
    document = Document(
        children=[
            Figure(
                children=[Paragraph(content=[Image(url="fig1.png")])],
                caption="Fig. 1 A bound figure caption.",
            ),
            Table(
                rows=[TableRow(cells=[TableCell(content=[Text(content="A")])])],
                caption="Table 1 A bound table caption.",
            ),
            Paragraph(content=[Image(url="fig2.png", caption="An inline image caption.")]),
        ]
    )

    projection = project_ast(document)

    # Every caption lands as an ordinary text block, in document order, content before its
    # caption -- exactly how the annotation side reads a printed caption. The empty
    # strings are the image-bearing paragraphs themselves, unchanged from before.
    assert projection.text_blocks == (
        "",
        "Fig. 1 A bound figure caption.",
        "A",
        "Table 1 A bound table caption.",
        "",
        "An inline image caption.",
    )
    assert projection.block_kinds == (
        "text_block",
        "text_block",
        "table",
        "text_block",
        "text_block",
        "text_block",
    )
    # The caption must not leak into the table's *cell* text: the annotation side keeps
    # table_caption outside the table HTML, so folding it in would corrupt the
    # table-content dimension while flattering the text one.
    assert projection.tables == (TableProjection(1, 1, 1, "A"),)


def test_a_caption_free_ast_projects_exactly_as_before() -> None:
    """The caption path must not disturb documents that carry none."""
    document = Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            Figure(children=[Paragraph(content=[Text(content="Panel text")])]),
            Paragraph(content=[Image(url="plain.png")]),
        ]
    )

    projection = project_ast(document)

    assert projection.text_blocks == ("Title", "Panel text", "")
    assert projection.block_kinds == ("title", "text_block", "text_block")


def test_a_definition_terms_text_survives_projection() -> None:
    """A definition term is page text, and used to vanish from measurement (#443).

    ``DefinitionTerm`` holds inline content *directly*, with no ``Paragraph`` wrapper, so
    a walk that recognises only block types descended straight past it into
    ``Text``/``Emphasis`` and yielded nothing. Its sibling ``DefinitionDescription``
    survived only because it happens to wrap its content in a ``Paragraph`` -- so half of
    every definition list was scored as if it had never been emitted. On the held-out
    110-article corpus that hid 130 words across 3 all2md files and 1 word of docling's.
    """
    document = Document(
        children=[
            DefinitionList(
                items=[
                    (
                        DefinitionTerm(
                            content=[
                                Text(content="Bastin GN, Sparrow AD (1999)."),
                                Emphasis(content=[Text(content="Rangeland Information System")]),
                            ]
                        ),
                        [DefinitionDescription(content=[Paragraph(content=[Text(content="preparing for change.")])])],
                    )
                ]
            )
        ]
    )

    projection = project_ast(document)

    # Two blocks, term before description: the term is admitted whole rather than shredded
    # into its Text and Emphasis pieces, which would have counted one term as two blocks
    # and moved the block-structure dimension for a change that adds no content.
    assert projection.text_blocks == (
        "Bastin GN, Sparrow AD (1999). Rangeland Information System",
        "preparing for change.",
    )
    assert projection.block_kinds == ("text_block", "text_block")


def test_any_container_of_inline_text_is_projected_whatever_its_type() -> None:
    """The admission tests the *shape*, not a list of type names (#443).

    ``DefinitionTerm`` is only the node that happened to expose this. Any container that
    holds inline content with no block-level node inside it has the same blindness, so the
    projection admits it by that property -- otherwise the next node type built to the same
    shape reproduces the bug in silence, and an instrument that cannot see part of its
    input is a bad instrument at any magnitude.
    """
    document = Document(
        children=[
            ListItem(children=[Text(content="An item that skipped its paragraph wrapper.")]),
            ListItem(children=[Paragraph(content=[Text(content="An item that did not.")])]),
        ]
    )

    projection = project_ast(document)

    assert projection.text_blocks == (
        "An item that skipped its paragraph wrapper.",
        "An item that did not.",
    )
    assert projection.block_kinds == ("text_block", "text_block")


def test_a_comment_is_never_page_text() -> None:
    """Markup that never prints must stay invisible, or two baselines inflate (#443).

    This is the boundary the shape rule has to respect: a comment carries text and holds no
    block-level node, so admitting "anything with inline text" would sweep it in. On the
    held-out corpus that would newly credit docling with 976 ``<!-- image -->`` markers
    across 106 of 110 articles and pymupdf4llm with 359 -- text no reader ever sees,
    counted against ground truth that never contains it.
    """
    document = Document(
        children=[
            Comment(content="image"),
            Paragraph(content=[Text(content="Real page text.")]),
        ]
    )

    projection = project_ast(document)

    assert projection.text_blocks == ("Real page text.",)
    assert projection.block_kinds == ("text_block",)


def test_page_scores_have_exact_independent_dimension_semantics() -> None:
    """Each metric must react to the fact it names rather than a shared output-length proxy."""
    expected = PageProjection(
        text_blocks=("A B",),
        block_kinds=("title", "text_block", "table"),
        tables=(TableProjection(2, 2, 4, "A B"),),
        formulas=(FormulaProjection("block", "$$x$$"),),
    )
    actual = PageProjection(
        text_blocks=("AB",),
        block_kinds=("title", "table"),
        tables=(TableProjection(1, 2, 2, "AB"),),
        formulas=(),
    )

    scores = score_page(expected, actual)

    assert scores == {
        "text_content_similarity": pytest.approx(2 / 3),
        # "A B" is located in "AB" on two of its three characters, which clears the
        # identification floor, and one located block cannot be out of order.
        "reading_order_similarity": 1.0,
        # One of three kinds dropped. This is the dimension the kind sequence answers;
        # it used to be folded into the reading-order score, which made that score react
        # to segmentation rather than to order.
        "block_structure_similarity": pytest.approx(2 / 3),
        "formula_presence_accuracy": 0.0,
        "table_structure_similarity": pytest.approx(2 / 3),
        "table_content_similarity": pytest.approx(2 / 3),
        "formula_content_similarity": 0.0,
    }


def test_latin_word_boundary_loss_is_penalized_but_cjk_glyph_spacing_is_not() -> None:
    """Losing every inter-word space must cost score; OCR's inter-glyph CJK spaces must not.

    Deleting all whitespace made 'thequickbrownfox' score a perfect 1.0 against
    'the quick brown fox' on the 316 predominantly-Latin pinned pages, so a parser that
    regressed to space-free extraction kept full credit. The CJK rationale is real -- OCR
    inserts spurious spaces between ideographs -- so whitespace is deleted only where it
    touches ideographic text and collapsed to a single space everywhere else.
    """
    latin = PageProjection(("the quick brown fox",), ("text_block",), (), ())
    spaceless = PageProjection(("thequickbrownfox",), ("text_block",), (), ())
    assert score_page(latin, spaceless)["text_content_similarity"] < 0.85

    cjk = PageProjection(("发票金额合计",), ("text_block",), (), ())
    spaced_cjk = PageProjection(("发 票 金 额 合 计",), ("text_block",), (), ())
    assert score_page(cjk, spaced_cjk)["text_content_similarity"] == 1.0


def test_every_text_bearing_annotation_category_is_ground_truth() -> None:
    """A parser must not score higher for dropping captions, headers, footers, or references.

    The dataset annotates text in eleven categories beyond text_block/title/code_txt. Scoring
    only that subset compared a filtered ground truth against the whole-page AST, so losing
    9.3% of the corpus text scored 1.0 while perfect fidelity scored 0.82 -- and on 63 pinned
    pages perfect fidelity scored exactly 0.0. The projection must cover the whole page.
    """
    assert {
        "equation_caption",
        "figure_caption",
        "figure_footnote",
        "footer",
        "header",
        "page_footnote",
        "page_number",
        "reference",
        "table_caption",
        "table_footnote",
    } <= oracles.TEXT_CATEGORIES

    record = {
        "page_info": {
            "page_no": 0,
            "image_path": "p.jpg",
            "height": 10,
            "width": 10,
            "page_attribute": {"data_source": "testsource"},
        },
        "layout_dets": [
            {"category_type": "header", "text": "Journal of Things", "order": 0},
            {"category_type": "text_block", "text": "Body", "order": 1},
            {"category_type": "figure_caption", "text": "Figure 1. A plot", "order": 2},
            {"category_type": "page_number", "text": "7", "order": 3},
        ],
    }

    truth = oracles.project_annotation(record)

    assert truth.projection.text_blocks == ("Journal of Things", "Body", "Figure 1. A plot", "7")
    assert truth.projection.block_kinds == ("text_block",) * 4
    assert truth.unscored_categories == {}

    dropped = PageProjection(("Body",), ("text_block",), (), ())
    assert score_page(truth.projection, dropped)["text_content_similarity"] < 0.3


def test_formula_similarity_preserves_latex_case_and_semantic_whitespace() -> None:
    """Text normalization must not conflate distinct case-sensitive LaTeX."""
    expected = PageProjection((), (), (), (FormulaProjection("block", r"\Gamma"),))

    case_score = score_page(
        expected,
        PageProjection((), (), (), (FormulaProjection("block", r"\gamma"),)),
    )
    whitespace_score = score_page(
        PageProjection((), (), (), (FormulaProjection("block", r"\text{a b}"),)),
        PageProjection((), (), (), (FormulaProjection("block", r"\text{ab}"),)),
    )
    delimited_score = score_page(
        PageProjection((), (), (), (FormulaProjection("block", "$$x + y$$"),)),
        PageProjection((), (), (), (FormulaProjection("block", "x + y"),)),
    )

    assert case_score["formula_content_similarity"] < 1.0
    assert whitespace_score["formula_content_similarity"] < 1.0
    assert delimited_score["formula_content_similarity"] == 1.0


def test_table_alignment_recovers_later_exact_matches_without_reordering() -> None:
    """An early omission must not shift every later table comparison, and swaps must not score as exact."""
    alpha = TableProjection(1, 1, 1, "alpha")
    beta = TableProjection(1, 1, 1, "beta")
    expected = PageProjection((), ("table", "table"), (alpha, beta), ())

    omitted = score_page(expected, PageProjection((), ("table",), (beta,), ()))
    reversed_order = score_page(expected, PageProjection((), ("table", "table"), (beta, alpha), ()))
    exact = score_page(expected, PageProjection((), ("table", "table"), (alpha, beta), ()))

    assert omitted["table_content_similarity"] == pytest.approx(0.5)
    assert exact["table_content_similarity"] == 1.0
    assert reversed_order["table_content_similarity"] == pytest.approx(0.2)
    assert reversed_order["table_structure_similarity"] == 1.0


def test_formula_metrics_are_absent_when_no_page_side_has_a_formula() -> None:
    """A parser with no math capability must not bank credit from formula-free pages."""
    plain = PageProjection(("Body",), ("text_block",), (), ())

    assert score_page(plain, plain) == {
        "text_content_similarity": 1.0,
        "reading_order_similarity": 1.0,
        "block_structure_similarity": 1.0,
    }

    missed = score_page(
        PageProjection((), (), (), (FormulaProjection("block", "a"),)),
        plain,
    )
    assert missed["formula_presence_accuracy"] == 0.0
    assert missed["formula_content_similarity"] == 0.0


def test_formula_alignment_matches_only_like_kinds_in_document_order() -> None:
    """Inline and block formulas are distinct even when their LaTeX is identical."""
    expected = PageProjection(
        (),
        (),
        (),
        (
            FormulaProjection("inline", "a"),
            FormulaProjection("block", "b"),
        ),
    )

    omitted_inline = score_page(
        expected,
        PageProjection((), (), (), (FormulaProjection("block", "b"),)),
    )
    wrong_kind = score_page(
        PageProjection((), (), (), (FormulaProjection("inline", "x"),)),
        PageProjection((), (), (), (FormulaProjection("block", "x"),)),
    )

    assert omitted_inline["formula_content_similarity"] == pytest.approx(0.5)
    assert wrong_kind["formula_presence_accuracy"] == 1.0
    assert wrong_kind["formula_content_similarity"] == 0.0


def test_text_similarity_normalizes_unicode_and_layout_whitespace() -> None:
    """CJK OCR spacing and compatibility glyphs must not masquerade as content loss."""
    assert content_similarity("Ａ 中\n文", "a中文") == 1.0
    assert content_similarity("abc", "") == 0.0
    assert content_similarity("", "") == 1.0


def test_text_similarity_is_exact_normalized_levenshtein() -> None:
    """Substitutions and insertions must have the documented edit-distance cost."""
    assert content_similarity("kitten", "sitting") == pytest.approx(4 / 7)


def _reference_edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, 1):
        current = [left_index]
        for right_index, right_character in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


@pytest.mark.fuzzing
@settings(deadline=None)
@given(
    st.text(alphabet="abc中文", max_size=8),
    st.text(alphabet="abc中文", max_size=8),
)
def test_bit_parallel_edit_distance_matches_reference(left: str, right: str) -> None:
    """The optimized Unicode oracle must equal the simple dynamic-programming contract.

    The example budget is deliberately left to the repository's Hypothesis profile, so a pull
    request draws the ``dev`` count and the scheduled ``HYPOTHESIS_PROFILE=ci`` run draws more.
    Pinning ``max_examples`` here would override that profile on every leg, which is what #230
    measured as roughly 160 times more expensive in CI than locally.

    Short draws cannot exercise the bit-parallel pattern's carry behaviour, so
    :func:`test_edit_distance_is_exact_across_machine_word_boundaries` covers length explicitly.
    """
    assert oracles._edit_distance(left, right) == _reference_edit_distance(left, right)


@pytest.mark.parametrize("length", [1, 31, 32, 33, 63, 64, 65, 66, 127, 128, 129, 200])
def test_edit_distance_is_exact_across_machine_word_boundaries(length: int) -> None:
    """Length must not change the answer, including where a bit-parallel pattern would carry.

    ``_edit_distance`` is Myers' bit-vector algorithm over Python integers. Those are unbounded,
    so there is no 64-bit block to get wrong, but nothing proved that: the property test above
    draws at most 8 characters, so no number of examples ever crossed a word boundary. The pinned
    corpus carries strings up to 2482 characters, so the untested range is the operational one.
    """
    left = "ab中文x" * (length // 5 + 1)
    left = left[:length]
    assert oracles._edit_distance(left, left) == 0
    assert oracles._edit_distance(left, "") == length
    substituted = ("z" if left[-1] != "z" else "y") + left[1:]
    assert oracles._edit_distance(left, substituted) == _reference_edit_distance(left, substituted)
    deleted = left[:-1]
    assert oracles._edit_distance(left, deleted) == _reference_edit_distance(left, deleted)
    reversed_text = left[::-1]
    assert oracles._edit_distance(left, reversed_text) == _reference_edit_distance(left, reversed_text)


def test_recovering_table_text_beats_deleting_the_table() -> None:
    """A parser must never score higher for dropping a table than for recovering its cells.

    Ground truth put table cell text only in ``tables``, while the AST side left it in
    ``text_blocks`` whenever no real ``Table`` node was built. On all 317 pinned pages with table
    ground truth, deleting the table beat emitting its cells as a paragraph -- by a full point on
    some pages. Cell text now belongs to the text stream on both sides.
    """
    html = "<table><tr><td>Alpha</td><td>Beta</td></tr></table>"
    truth = oracles.project_annotation(
        {
            "page_info": {
                "page_no": 0,
                "image_path": "p.jpg",
                "height": 100,
                "width": 100,
                "page_attribute": {"data_source": "testsource"},
            },
            "layout_dets": [
                {"category_type": "text_block", "text": "Body", "order": 0, "poly": [0, 10] * 4},
                {"category_type": "table", "html": html, "order": 1, "poly": [0, 50] * 4},
            ],
        }
    ).projection

    assert truth.text_blocks == ("Body", "Alpha Beta")

    kept_as_text = PageProjection(("Body", "Alpha Beta"), ("text_block", "text_block"), (), ())
    deleted = PageProjection(("Body",), ("text_block",), (), ())

    kept = score_page(truth, kept_as_text)["text_content_similarity"]
    dropped = score_page(truth, deleted)["text_content_similarity"]
    assert kept == 1.0
    assert dropped < kept


def test_unordered_running_content_is_placed_by_geometry() -> None:
    """Dropping a header must not outscore emitting it in its true position.

    Every header, footer, page number, and page footnote in the pinned dataset carries
    ``order: null``. Sorting those last appended running content after the body, so a parser that
    emitted the header first mismatched the ground truth and a parser that deleted the header
    matched it better -- a mean inversion on 663 of 981 pages. A category-only rank is not enough:
    about one page number in seven sits at the top of the page.
    """
    record = {
        "page_info": {
            "page_no": 0,
            "image_path": "p.jpg",
            "height": 1000,
            "width": 800,
            "page_attribute": {"data_source": "testsource"},
        },
        "layout_dets": [
            {"category_type": "text_block", "text": "Body", "order": 5, "poly": [0, 400] * 4},
            {"category_type": "header", "text": "Journal", "order": None, "poly": [0, 40] * 4},
            {"category_type": "footer", "text": "Copyright", "order": None, "poly": [0, 960] * 4},
            {"category_type": "page_number", "text": "7", "order": None, "poly": [0, 20] * 4},
        ],
    }

    truth = oracles.project_annotation(record).projection

    assert truth.text_blocks == ("7", "Journal", "Body", "Copyright")

    visual = PageProjection(truth.text_blocks, truth.block_kinds, (), ())
    without_header = PageProjection(("7", "Body", "Copyright"), ("text_block",) * 3, (), ())
    assert score_page(truth, visual)["text_content_similarity"] == 1.0
    assert score_page(truth, without_header)["text_content_similarity"] < 1.0


def test_reversed_output_cannot_score_a_perfect_reading_order() -> None:
    """Reading order must detect reordering, not just block-category coverage.

    Eleven text categories collapse to ``text_block``, so an edit similarity over the kind
    sequence returned exactly 1.0 for fully reversed output on 153 pinned pages, and every
    permutation was free on the 113 pages whose kinds are a single repeated token.
    """
    expected = PageProjection(("Alpha", "Beta", "Gamma"), ("text_block",) * 3, (), ())
    forward = PageProjection(("Alpha", "Beta", "Gamma"), ("text_block",) * 3, (), ())
    reversed_blocks = PageProjection(("Gamma", "Beta", "Alpha"), ("text_block",) * 3, (), ())

    assert score_page(expected, forward)["reading_order_similarity"] == 1.0
    assert score_page(expected, reversed_blocks)["reading_order_similarity"] == 0.0


def test_spurious_spaces_around_fullwidth_punctuation_are_ignored() -> None:
    """Correct CJK extraction must not be penalized for the OCR artefact the rule targets.

    NFKC folds fullwidth punctuation to ASCII, so running the whitespace deletion only after
    normalization left spurious spaces beside those glyphs in place and depressed the score on
    588 of the 743 pinned pages containing them; it now costs score on none. The substitution runs
    on both sides of NFKC.
    """
    tight = PageProjection(("（6）计算：",), ("text_block",), (), ())
    spaced = PageProjection((" （ 6 ） 计算 ： ",), ("text_block",), (), ())
    assert score_page(tight, spaced)["text_content_similarity"] == 1.0

    latin = PageProjection(("the quick brown fox",), ("text_block",), (), ())
    spaceless = PageProjection(("thequickbrownfox",), ("text_block",), (), ())
    assert score_page(latin, spaceless)["text_content_similarity"] < 0.85


def test_inline_equations_inside_code_are_not_ground_truth() -> None:
    """A ``CodeBlock`` holds a plain string, so a formula inside code can never be matched.

    Harvesting that span created ground truth no AST can satisfy, which showed up as the last
    residual monotonicity inversion: a degraded parser outscored perfect fidelity on formula
    presence for one pinned page.

    The span shape here is the one the pinned dataset actually uses: ``line_with_spans`` is a flat
    list of spans carrying ``category_type`` directly. All 69718 spans in the pinned annotation
    are that shape and none nests them under a ``spans`` key, so a nested fixture would be skipped
    before reaching the guard and would pass with the guard deleted.
    """
    record = {
        "page_info": {
            "page_no": 0,
            "image_path": "p.jpg",
            "height": 100,
            "width": 100,
            "page_attribute": {"data_source": "testsource"},
        },
        "layout_dets": [
            {
                "category_type": "code_txt",
                "text": "x = $a$",
                "order": 0,
                "poly": [0, 10] * 4,
                "line_with_spans": [{"category_type": "equation_inline", "latex": "$a$"}],
            }
        ],
    }

    truth = oracles.project_annotation(record)

    assert truth.projection.formulas == ()
    assert truth.projection.text_blocks == ("x = $a$",)


def test_identical_output_scores_a_perfect_reading_order_despite_repeated_blocks() -> None:
    """Byte-identical output must be the ceiling, so the order term cannot self-penalize.

    Matching each emitted block to its most similar ground-truth block by unconstrained argmax
    sent every repetition of one string to the same index, which registered as an inversion and
    capped self-comparison at 0.9973 across the pinned corpus. Ties now resolve towards the
    block's own position.
    """
    page = PageProjection(("Same", "Same", "Same", "Tail"), ("text_block",) * 4, (), ())
    assert score_page(page, page)["reading_order_similarity"] == 1.0


def test_unrecognizable_blocks_cannot_outscore_correct_content_in_the_wrong_order() -> None:
    """Destroying every block's content must not buy a better reading order than reversing it.

    Ties in the block match resolve towards the block's own position, so when nothing resembles
    a block the identity mapping falls out of the tie-break alone and the inversion count is
    zero. Ten empty paragraphs scored a perfect 1.0 and ten junk paragraphs 1.0, against 0.0 for
    emitting all ten correctly but reversed -- the metric ranked a parser that produced nothing
    above one that produced everything. Every degraded variant checked before shipping *deleted*
    blocks, which left the whole right-shape/wrong-payload quadrant untested.
    """
    blocks = tuple(f"Paragraph {index} with enough text to match on" for index in range(10))
    kinds = ("text_block",) * 10
    expected = PageProjection(blocks, kinds, (), ())

    perfect = score_page(expected, expected)["reading_order_similarity"]
    reversed_content = score_page(expected, PageProjection(blocks[::-1], kinds, (), ()))
    empty = score_page(expected, PageProjection(("",) * 10, kinds, (), ()))
    junk = score_page(expected, PageProjection(("zzz",) * 10, kinds, (), ()))

    assert perfect == 1.0
    assert reversed_content["reading_order_similarity"] == 0.0
    assert empty["reading_order_similarity"] == 0.0
    assert junk["reading_order_similarity"] == 0.0
    # The content dimension already reds on these, and must keep saying so independently.
    assert empty["text_content_similarity"] == 0.0
    assert junk["text_content_similarity"] < 0.1


def test_a_single_unrecognizable_block_earns_no_reading_order_credit() -> None:
    """One block has no order to get wrong, but it still has to be the block it claims to be.

    The order term used to be skipped entirely below two blocks, so a page answered with a single
    junk paragraph collected the full block-kind coverage score -- the same 1.0 that byte-perfect
    output earns. Identification is charged at every block count; only the inversion count needs
    a pair.
    """
    expected = PageProjection(("The quick brown fox jumps",), ("text_block",), (), ())

    assert score_page(expected, expected)["reading_order_similarity"] == 1.0
    assert score_page(expected, PageProjection(("zzz",), ("text_block",), (), ()))["reading_order_similarity"] == 0.0


def test_ordinary_extraction_noise_does_not_bleed_into_the_order_term() -> None:
    """The identification floor must not turn reading order into a second content metric.

    A block recognizably the same text, with the extraction damage the real corpus shows, has to
    keep its vote -- otherwise every content regression reds two dimensions and the ratchet loses
    the one signal that is only about sequence.
    """
    expected = PageProjection(("Alpha beta gamma", "Delta epsilon zeta"), ("text_block",) * 2, (), ())
    noisy = PageProjection(("Alpha beta gamm", "Delta epsilonzeta"), ("text_block",) * 2, (), ())
    swapped = PageProjection(("Delta epsilon zeta", "Alpha beta gamma"), ("text_block",) * 2, (), ())

    assert score_page(expected, noisy)["reading_order_similarity"] == 1.0
    assert score_page(expected, noisy)["text_content_similarity"] < 1.0
    assert score_page(expected, swapped)["reading_order_similarity"] == 0.0


def test_reading_order_does_not_depend_on_how_the_output_was_chunked() -> None:
    """Splitting or merging blocks moves no text, so it must not move the order score.

    Pairing emitted blocks one-to-one against ground-truth blocks measured segmentation and
    called it order. Text reproduced exactly but emitted as a single block scored 0.0, and
    splitting every block in two scored 0.44. On the pinned corpus that left 894 of 981 pages at
    exactly zero, 128 of them scoring 0.9 or better on text content -- the metric had no dynamic
    range left to detect a regression with. Ground-truth blocks are now located inside the
    concatenated output, which is blind to chunking.
    """
    blocks = ("Alpha beta gamma", "Delta epsilon zeta", "Eta theta iota")
    expected = PageProjection(blocks, ("text_block",) * 3, (), ())

    merged = PageProjection((" ".join(blocks),), ("text_block",), (), ())
    split = PageProjection(
        tuple(part for block in blocks for part in (block[: len(block) // 2], block[len(block) // 2 :])),
        ("text_block",) * 6,
        (),
        (),
    )

    assert score_page(expected, merged)["reading_order_similarity"] == 1.0
    assert score_page(expected, split)["reading_order_similarity"] == 1.0
    # ...and reordering the merged text still costs everything, so the insensitivity is to
    # chunking only.
    reversed_merged = PageProjection((" ".join(reversed(blocks)),), ("text_block",), (), ())
    assert score_page(expected, reversed_merged)["reading_order_similarity"] == 0.0


def test_block_structure_is_scored_separately_from_reading_order() -> None:
    """Segmentation is a real question, and it is not the same question as ordering.

    The block-kind sequence used to be a factor of the reading-order score, which is how
    chunking got back into a metric that had just been made blind to it: four blocks correctly
    merged into one scored 0.25 on order for no reason connected to order. It is now its own
    dimension -- and it cannot answer the ordering question itself, because eleven text
    categories collapse to ``text_block``, so reversed output scores a perfect 1.0 on it.
    """
    blocks = ("Alpha beta gamma", "Delta epsilon zeta", "Eta theta iota")
    expected = PageProjection(blocks, ("text_block",) * 3, (), ())
    merged = PageProjection((" ".join(blocks),), ("text_block",), (), ())
    reversed_blocks = PageProjection(tuple(reversed(blocks)), ("text_block",) * 3, (), ())

    assert score_page(expected, merged)["block_structure_similarity"] == pytest.approx(1 / 3)
    assert score_page(expected, merged)["reading_order_similarity"] == 1.0

    assert score_page(expected, reversed_blocks)["block_structure_similarity"] == 1.0
    assert score_page(expected, reversed_blocks)["reading_order_similarity"] == 0.0


def test_a_block_fragmented_by_character_level_noise_is_still_located() -> None:
    """A block damaged throughout has not moved, and must not read as missing.

    Scoring only the longest unbroken run of matched characters made a substitution as ordinary
    as ``o`` for ``0`` -- which OCR makes constantly -- shatter a block into fragments too short
    to clear the identification floor, so the block dropped out of the ordering entirely. Every
    aligned character counts now.
    """
    blocks = ("The quick brown fox", "jumps over the lazy dog")
    expected = PageProjection(blocks, ("text_block",) * 2, (), ())
    damaged = PageProjection(tuple(block.replace("o", "0") for block in blocks), ("text_block",) * 2, (), ())

    assert score_page(expected, damaged)["reading_order_similarity"] == 1.0
    assert score_page(expected, damaged)["text_content_similarity"] < 1.0


def test_a_paragraph_holding_table_cells_costs_exactly_one_kind_substitution() -> None:
    """Recovering a table as a paragraph must be charged for segmentation and nothing else.

    The expected cost is one substitution in the block-kind sequence, ``1 - 1/n``, and it lands
    on ``block_structure_similarity``. Because the table's cell text sits in both text streams,
    this variant's text is byte-identical to exact reproduction and in the same order, so the
    other two dimensions must be exactly 1.0. Anything lower would mean they double-charge a
    variant whose text and order are right, and the ratchet would red the first time all2md
    starts recovering table cells.
    """
    truth = PageProjection(
        ("Intro", "A B"),
        ("text_block", "table"),
        (TableProjection(1, 2, 2, "A B"),),
        (),
    )
    paragraph = PageProjection(("Intro", "A B"), ("text_block", "text_block"), (), ())

    scores = score_page(truth, paragraph)
    assert scores["text_content_similarity"] == 1.0
    assert scores["reading_order_similarity"] == 1.0
    assert scores["block_structure_similarity"] == 1 - 1 / len(truth.block_kinds)

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_render_error_contract.py
"""``from_ast`` must fail with an ``All2MdError``, whatever the renderer raises.

Renderers delegate to third-party libraries — python-pptx, pyth, odfpy — that
raise their own exception types. Some renderers translated those and some did
not, so ``from_ast(doc, "pptx")`` could raise a bare ``ValueError`` at a caller
who had written the documented ``except All2MdError``. Issue #212.

The gate here is the probe below rather than a list of documents known to break
particular renderers. Those documents are the subject of #206-#211 and will stop
raising as each is fixed, taking the coverage with them; the contract has to hold
for *any* failure, including ones no current document produces.
"""

from __future__ import annotations

import pytest

from all2md import from_ast, roundtrippable_formats
from all2md.ast.nodes import Document, Paragraph, Text
from all2md.exceptions import All2MdError, DependencyError
from all2md.renderers.rtf import RtfRenderer

pytestmark = [pytest.mark.unit, pytest.mark.matrix_single]


#: Formats whose renderers emit tabular data and legitimately ignore a prose
#: node, so the probe never reaches them. Listing them explicitly means a *text*
#: renderer that quietly stops walking the tree fails the test rather than
#: passing it vacuously.
NON_PROSE_FORMATS = frozenset({"csv", "ini", "json", "toml", "yaml"})


class ProbeError(RuntimeError):
    """Sentinel standing in for an arbitrary third-party library exception.

    ``RuntimeError`` deliberately: it is not an ``All2MdError``, and it is not in
    the ``(NotImplementedError, AttributeError)`` pair the pipeline treats as
    "this renderer does not offer that output mode".
    """


class ProbeNode(Paragraph):
    """A paragraph that raises when visited.

    Raising from ``accept`` rather than from a specific ``visit_*`` method means
    the probe fires wherever a renderer walks the tree, without depending on how
    any one renderer dispatches.
    """

    def accept(self, visitor: object) -> object:  # type: ignore[override]
        raise ProbeError("probe")


def _probe_document() -> Document:
    """A document with one ordinary block, then the probe."""
    return Document(children=[Paragraph(content=[Text(content="before")]), ProbeNode(content=[])])


@pytest.mark.parametrize("fmt", sorted(roundtrippable_formats()))
def test_renderer_exceptions_surface_as_all2mderror(fmt: str) -> None:
    """No renderer lets a foreign exception escape ``from_ast``.

    Parametrised over the registry rather than a hand-written tuple, so a format
    added later is covered without anyone remembering to add it here.
    """
    try:
        from_ast(_probe_document(), fmt)
    except DependencyError:
        pytest.skip(f"{fmt} renderer's optional dependencies are not installed")
    except ProbeError as exc:  # pragma: no cover - this is the regression
        raise AssertionError(
            f"{fmt}: renderer let a bare {type(exc).__name__} escape from_ast; "
            f"a caller writing `except All2MdError` would crash"
        ) from exc
    except All2MdError:
        pass
    except Exception as exc:  # noqa: BLE001 - the assertion is about the class
        raise AssertionError(f"{fmt}: from_ast raised {type(exc).__name__}, which is not an All2MdError") from exc
    else:
        # Nothing raised, so the renderer never visited the probe. That is only
        # defensible for the data formats, which read tables and skip prose.
        assert fmt in NON_PROSE_FORMATS, (
            f"{fmt}: the probe never fired, so this format is not actually being "
            f"tested. Either the renderer silently drops content, or it belongs "
            f"in NON_PROSE_FORMATS with a reason."
        )


def test_renderer_specific_errors_are_not_reflattened() -> None:
    """A renderer that already reports well keeps its own message.

    The pipeline wraps what reaches it, so it must not replace the message of a
    renderer that already raised an ``All2MdError``. DOCX is the reference
    implementation: it wraps its own body and names the format.

    Driven by the probe rather than a document that breaks DOCX specifically.
    This test used the spanning-cell table from #207 until that was fixed, which
    is the attrition the module docstring warns about.
    """
    with pytest.raises(All2MdError) as excinfo:
        from_ast(_probe_document(), "docx")
    assert "Failed to render DOCX" in str(excinfo.value)


def test_rtf_render_to_string_wraps_its_body() -> None:
    """RTF reports a failure on the path a text format actually takes.

    RTF is the case the split entry points hid: ``render`` wrapped its body but
    ``render_to_string`` — the path the pipeline uses for a text format — did
    not, so a failure escaped unwrapped.

    Driven by the probe rather than #210's task-list document, which stopped
    raising once that was fixed. This is the attrition the module docstring
    warns about; the contract outlives any particular document that broke it.
    """
    renderer = RtfRenderer()
    with pytest.raises(All2MdError):
        renderer.render_to_string(_probe_document())

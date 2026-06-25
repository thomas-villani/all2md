"""Unit tests for CLI processor utilities."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import Any

import pytest

from all2md.cli import processors
from all2md.cli.processors import (
    EXIT_SUCCESS,
    build_transform_instances,
    convert_single_file,
)
from all2md.converter_registry import registry


@pytest.fixture
def dummy_transform_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Provide a stub transform registry for CLI processor tests."""
    metadata_instances: list[Any] = []
    registry_instances: list[Any] = []

    class DummyTransform:
        pass

    class DummyMetadata:
        parameters: dict[str, Any] = {}

        def create_instance(self, **_: Any) -> DummyTransform:
            instance = DummyTransform()
            metadata_instances.append(instance)
            return instance

    class DummyRegistry:
        def get_metadata(self, name: str) -> DummyMetadata:
            return DummyMetadata()

        def get_transform(self, name: str, **_: Any) -> DummyTransform:
            instance = DummyTransform()
            registry_instances.append(instance)
            return instance

    stub_registry = DummyRegistry()
    # Patch both the module-level import and the processors import
    monkeypatch.setattr("all2md.transforms.registry", stub_registry)
    monkeypatch.setattr("all2md.cli.processors.transform_registry", stub_registry)

    return {
        "metadata_instances": metadata_instances,
        "registry_instances": registry_instances,
        "transform_class": DummyTransform,
    }


@pytest.mark.unit
def test_build_transform_instances_records_transform_specs(dummy_transform_registry) -> None:
    """CLI transform builder should persist serializable transform specs."""
    args = argparse.Namespace(transforms=["demo-transform"], _provided_args=set())

    transforms = build_transform_instances(args)

    assert transforms is not None and len(transforms) == 1
    assert isinstance(transforms[0], dummy_transform_registry["transform_class"])
    assert dummy_transform_registry["metadata_instances"]
    assert getattr(args, "transform_specs", None) == [{"name": "demo-transform", "params": {}}]


@pytest.mark.unit
def test_convert_single_file_rebuilds_transforms_from_specs(
    dummy_transform_registry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """convert_single_file should materialize transforms from serialized specs."""
    from all2md.cli.input_items import CLIInputItem

    captured: dict[str, Any] = {}

    def fake_convert(source, output=None, **kwargs):  # type: ignore[no-untyped-def]
        # Capture transforms parameter
        captured["transforms"] = kwargs.get("transforms")
        # Return None to indicate success (content written to output)
        return None

    monkeypatch.setattr(processors, "convert", fake_convert)
    monkeypatch.setattr(processors, "prepare_options_for_execution", lambda *args, **kwargs: {})

    input_path = tmp_path / "sample.pdf"
    input_path.write_text("stub")
    output_path = tmp_path / "output.md"

    # Create CLIInputItem instead of using Path directly
    input_item = CLIInputItem(
        raw_input=input_path,
        kind="local_file",
        display_name=input_path.name,
        path_hint=input_path,
    )

    specs = [{"name": "demo-transform", "params": {}}]

    exit_code, _, error = convert_single_file(
        input_item,
        output_path,
        options={},
        format_arg="markdown",
        transforms=None,
        show_progress=False,
        target_format="markdown",
        transform_specs=specs,
    )

    assert exit_code == EXIT_SUCCESS, f"Expected EXIT_SUCCESS but got {exit_code}, error: {error}"
    assert error is None

    rebuilt = captured.get("transforms")
    assert rebuilt and len(rebuilt) == 1
    assert isinstance(rebuilt[0], dummy_transform_registry["transform_class"])


@pytest.mark.unit
def test_convert_single_file_streams_respect_target_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Streaming conversions should honour requested renderer output."""
    from all2md.cli.input_items import CLIInputItem

    captured: dict[str, Any] = {}

    def fake_convert(*args, **kwargs):  # type: ignore[no-untyped-def]
        source = args[0] if args else None
        captured["source"] = source
        captured["output"] = kwargs.get("output")
        captured["source_format"] = kwargs.get("source_format")
        captured["target_format"] = kwargs.get("target_format")
        return "<html>payload</html>"

    monkeypatch.setattr(processors, "convert", fake_convert)
    monkeypatch.setattr(processors, "prepare_options_for_execution", lambda *args, **kwargs: {})

    input_path = tmp_path / "sample.txt"
    input_path.write_text("stub")

    input_item = CLIInputItem(
        raw_input=input_path,
        kind="local_file",
        display_name=input_path.name,
        path_hint=input_path,
    )

    exit_code, _, error = convert_single_file(
        input_item,
        output_path=None,
        options={},
        format_arg="txt",
        transforms=None,
        show_progress=False,
        target_format="html",
        transform_specs=None,
    )

    assert exit_code == EXIT_SUCCESS
    assert error is None
    assert captured["target_format"] == "html"

    std = capsys.readouterr()
    assert std.out.strip() == "<html>payload</html>"


@pytest.mark.unit
def test_apply_rich_formatting_honours_no_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Markdown rich rendering should respect the no-wrap flag."""
    pytest.importorskip("rich")

    from all2md.cli.processors import _apply_rich_formatting

    class DummyCapture:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def get(self):
            return "captured"

    class DummyConsole:
        def __init__(self):
            self.print_calls: list[bool | None] = []

        def print(self, _obj, *, no_wrap=None):
            self.print_calls.append(no_wrap)

        def capture(self):
            return DummyCapture()

    class DummyMarkdown:
        def __init__(self, content, **_kwargs):
            self.content = content

    dummy_console = DummyConsole()

    monkeypatch.setattr("rich.console.Console", lambda **_kwargs: dummy_console)
    monkeypatch.setattr("rich.markdown.Markdown", DummyMarkdown)

    args = argparse.Namespace(rich_no_word_wrap=True)
    text, is_rich = _apply_rich_formatting("data", args)

    assert text == "captured"
    assert is_rich is True
    assert dummy_console.print_calls == [True]


@pytest.mark.unit
def test_render_single_item_to_stdout_invokes_rich_syntax(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Non-markdown stdout rendering should delegate to rich syntax when available."""
    pytest.importorskip("rich")

    from all2md.cli.input_items import CLIInputItem

    call_args: dict[str, Any] = {}

    def fake_convert(*args, **kwargs):  # type: ignore[no-untyped-def]
        return "<html/>"

    def fake_render(text: str, args: argparse.Namespace, fmt: str) -> bool:
        call_args["text"] = text
        call_args["format"] = fmt
        call_args["no_wrap"] = getattr(args, "rich_no_word_wrap", False)
        return True

    monkeypatch.setattr(processors, "convert", fake_convert)
    monkeypatch.setattr(processors, "prepare_options_for_execution", lambda *args, **kwargs: {})
    monkeypatch.setattr(processors, "_render_rich_text_output", fake_render)

    input_path = tmp_path / "sample.eml"
    input_path.write_text("stub")

    item = CLIInputItem(
        raw_input=input_path,
        kind="local_file",
        display_name=input_path.name,
        path_hint=input_path,
    )

    args = argparse.Namespace(rich=True, pager=False, rich_no_word_wrap=False)

    exit_code = processors._render_single_item_to_stdout(
        item,
        args,
        options={},
        format_arg="eml",
        transforms=None,
        should_use_rich=True,
        target_format="html",
    )

    assert exit_code == EXIT_SUCCESS
    assert call_args["text"] == "<html/>"
    assert call_args["format"] == "html"
    assert call_args["no_wrap"] is False


@pytest.mark.unit
def test_registry_default_extension_uses_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry helper should respect metadata-provided extensions."""
    metadata = SimpleNamespace(extensions=["custom"])
    monkeypatch.setattr(registry, "get_format_info", lambda name: [metadata])

    assert registry.get_default_extension_for_format("docx") == ".custom"


@pytest.mark.unit
def test_registry_default_extension_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry helper should fall back to .<format> when metadata is missing."""
    monkeypatch.setattr(registry, "get_format_info", lambda name: None)

    assert registry.get_default_extension_for_format("pptx") == ".pptx"


@pytest.mark.unit
def test_apply_rich_formatting_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _apply_rich_formatting successfully renders markdown with Rich."""
    import argparse

    from all2md.cli.processors import _apply_rich_formatting

    args = argparse.Namespace(
        rich_code_theme="monokai",
        rich_inline_code_theme=None,
        rich_hyperlinks=True,
        rich_justify="left",
    )

    markdown = "# Test\nThis is **bold** text."

    # Mock Rich modules
    class MockCapture:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self):
            return "RICH_RENDERED_CONTENT"

    class MockConsole:
        def __init__(self, **kwargs):
            pass

        def capture(self):
            return MockCapture()

        def print(self, *args, **kwargs):
            pass

    class MockMarkdown:
        def __init__(self, content, **kwargs):
            pass

    import sys

    mock_rich = type(sys)("rich")
    mock_rich.console = type(sys)("console")
    mock_rich.console.Console = MockConsole
    mock_rich.markdown = type(sys)("markdown")
    mock_rich.markdown.Markdown = MockMarkdown

    monkeypatch.setitem(sys.modules, "rich", mock_rich)
    monkeypatch.setitem(sys.modules, "rich.console", mock_rich.console)
    monkeypatch.setitem(sys.modules, "rich.markdown", mock_rich.markdown)

    content, is_rich = _apply_rich_formatting(markdown, args)

    assert content == "RICH_RENDERED_CONTENT"
    assert is_rich is True


@pytest.mark.unit
def test_apply_rich_formatting_import_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Test _apply_rich_formatting handles ImportError gracefully."""
    import argparse
    import sys

    from all2md.cli.processors import _apply_rich_formatting

    args = argparse.Namespace()
    markdown = "# Test\nPlain markdown."

    # Remove rich from sys.modules to simulate ImportError
    for key in list(sys.modules.keys()):
        if key.startswith("rich"):
            monkeypatch.delitem(sys.modules, key, raising=False)

    # Prevent import of rich
    def import_blocker(name, *args, **kwargs):
        if name.startswith("rich"):
            raise ImportError(f"No module named '{name}'")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", import_blocker)

    content, is_rich = _apply_rich_formatting(markdown, args)

    assert content == markdown  # Should return plain markdown
    assert is_rich is False

    # Check warning was printed
    captured = capsys.readouterr()
    assert "Rich library not installed" in captured.err


@pytest.mark.unit
def test_generate_outline_from_document() -> None:
    """Test generate_outline_from_document produces correct markdown list."""
    from all2md.ast.nodes import Document, Heading, Text
    from all2md.cli.processors import generate_outline_from_document

    # Create document with nested headings
    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Heading(level=2, content=[Text(content="Background")]),
            Heading(level=3, content=[Text(content="Related Work")]),
            Heading(level=2, content=[Text(content="Motivation")]),
            Heading(level=1, content=[Text(content="Methods")]),
            Heading(level=2, content=[Text(content="Data Collection")]),
        ],
        metadata={},
    )

    outline = generate_outline_from_document(doc, max_level=6)

    expected = """* Introduction
  * Background
    * Related Work
  * Motivation
* Methods
  * Data Collection"""

    assert outline == expected


@pytest.mark.unit
def test_generate_outline_from_document_with_max_level() -> None:
    """Test generate_outline_from_document respects max_level parameter."""
    from all2md.ast.nodes import Document, Heading, Text
    from all2md.cli.processors import generate_outline_from_document

    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Heading(level=2, content=[Text(content="Section 1.1")]),
            Heading(level=3, content=[Text(content="Subsection 1.1.1")]),
            Heading(level=1, content=[Text(content="Chapter 2")]),
        ],
        metadata={},
    )

    # Only include up to level 2
    outline = generate_outline_from_document(doc, max_level=2)

    expected = """* Chapter 1
  * Section 1.1
* Chapter 2"""

    assert outline == expected


@pytest.mark.unit
def test_generate_outline_from_empty_document() -> None:
    """Test generate_outline_from_document handles documents with no headings."""
    from all2md.ast.nodes import Document, Paragraph, Text
    from all2md.cli.processors import generate_outline_from_document

    doc = Document(
        children=[
            Paragraph(content=[Text(content="Just a paragraph, no headings")]),
        ],
        metadata={},
    )

    outline = generate_outline_from_document(doc, max_level=6)

    assert outline == "No headings found in document"


def _outline_doc():
    """Build a small document used by the line-number tests."""
    from all2md.ast.nodes import Document, Heading, Paragraph, Text

    return Document(
        children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="Intro body.")]),
            Heading(level=2, content=[Text(content="Background")]),
            Paragraph(content=[Text(content="Background body.")]),
            Heading(level=1, content=[Text(content="Methods")]),
            Paragraph(content=[Text(content="Methods body.")]),
        ],
        metadata={},
    )


@pytest.mark.unit
def test_outline_with_line_numbers() -> None:
    """--outline --line-numbers annotates each heading with its output line."""
    from all2md.cli.processors import _outline_output

    out = _outline_output(_outline_doc(), max_level=6, line_numbers=True, effective_options={})

    expected = "\n".join(
        [
            "1: * Introduction",
            "5:   * Background",
            "9: * Methods",
        ]
    )
    assert out == expected


@pytest.mark.unit
def test_outline_line_numbers_match_full_render() -> None:
    """Outline line numbers point at the same lines as the full Markdown render."""
    from all2md.api import from_ast
    from all2md.cli.processors import _outline_output

    doc = _outline_doc()
    rendered = from_ast(doc, "markdown")
    assert isinstance(rendered, str)
    md_lines = rendered.split("\n")

    out = _outline_output(doc, max_level=6, line_numbers=True, effective_options={})
    for entry in out.splitlines():
        number, _, heading = entry.partition(": ")
        text = heading.lstrip(" *")
        # The reported line in the full render is the heading carrying that text.
        assert text in md_lines[int(number) - 1]


@pytest.mark.unit
def test_outline_line_numbers_max_level_filter() -> None:
    """max_level hides deeper headings but keeps true line numbers for the rest."""
    from all2md.cli.processors import _outline_output

    out = _outline_output(_outline_doc(), max_level=1, line_numbers=True, effective_options={})

    assert out == "1: * Introduction\n9: * Methods"


@pytest.mark.unit
def test_extract_by_line_range_markdown() -> None:
    """--extract line:X-Y slices the rendered Markdown by line range."""
    from all2md.cli.processors import _extraction_output

    result = _extraction_output(_outline_doc(), ["line:9-11"], "markdown", False, {}, None)

    assert result == "# Methods\n\nMethods body."


@pytest.mark.unit
def test_extract_by_line_range_with_line_numbers() -> None:
    """line: extraction with --line-numbers keeps the original line numbers."""
    from all2md.cli.processors import _extraction_output

    result = _extraction_output(_outline_doc(), ["line:9-11"], "markdown", True, {}, None)

    assert result == " 9: # Methods\n10: \n11: Methods body."


@pytest.mark.unit
def test_extract_by_line_range_noncontiguous() -> None:
    """A non-contiguous line: selection is separated by an unnumbered blank line."""
    from all2md.cli.processors import _extraction_output

    result = _extraction_output(_outline_doc(), ["line:1,9"], "markdown", True, {}, None)

    assert result == "1: # Introduction\n\n9: # Methods"


@pytest.mark.unit
def test_extract_by_lines_out_of_range_raises() -> None:
    """A line: spec selecting no real lines raises a helpful error."""
    from all2md.cli.processors import _extraction_output

    with pytest.raises(ValueError, match="No lines selected"):
        _extraction_output(_outline_doc(), ["line:500-600"], "markdown", False, {}, None)


@pytest.mark.unit
def test_extract_name_with_line_numbers_uses_original_lines() -> None:
    """Name extraction with --line-numbers reports the document's true line numbers."""
    from all2md.cli.processors import _extraction_output

    result = _extraction_output(_outline_doc(), ["Methods"], "markdown", True, {}, None)

    # The Methods section starts at line 9 in the full render (width 2: lines 9-11).
    assert result.splitlines()[0] == " 9: # Methods"


@pytest.mark.unit
def test_is_line_extract_spec() -> None:
    """The line: prefix is detected case-insensitively and tolerant of whitespace."""
    from all2md.cli.processors import is_line_extract_spec

    assert is_line_extract_spec("line:1-3")
    assert is_line_extract_spec("  LINE:5 ")
    assert not is_line_extract_spec("#:1-3")
    assert not is_line_extract_spec("Introduction")
    assert not is_line_extract_spec(None)


@pytest.mark.unit
def test_resolve_section_indices_matches_extract_sections() -> None:
    """resolve_section_indices selects the same sections extract_sections builds from."""
    from all2md.ast.sections import get_all_sections, resolve_section_indices

    sections = get_all_sections(_outline_doc(), min_level=1, max_level=6)

    assert resolve_section_indices(sections, "#:1-2") == [0, 1]
    assert resolve_section_indices(sections, "Methods") == [2]
    assert resolve_section_indices(sections, "*round*") == [1]  # matches "Background"

    with pytest.raises(ValueError, match="No sections match"):
        resolve_section_indices(sections, "Nonexistent")


@pytest.mark.unit
def test_determine_target_format_honors_explicit_to() -> None:
    """_determine_target_format (stdout path) returns an explicit --to value."""
    from all2md.cli.builder import create_parser
    from all2md.cli.processors import _determine_target_format

    parser = create_parser()

    args = parser.parse_args(["doc.md", "--to", "html"])
    assert _determine_target_format(args) == "html"

    # No explicit --to -> auto (lets downstream detect/default).
    args = parser.parse_args(["doc.md"])
    assert _determine_target_format(args) == "auto"


@pytest.mark.unit
def test_determine_output_format_explicit_to_overrides_extension() -> None:
    """An explicit --to wins over output-path extension inference."""
    from pathlib import Path

    from all2md.cli.builder import create_parser
    from all2md.cli.processors import _determine_output_format

    parser = create_parser()

    # Explicit --to markdown beats a .html output path.
    args = parser.parse_args(["doc.md", "--to", "markdown"])
    assert _determine_output_format(args, Path("out.html")) == "markdown"

    # Without --to, the extension drives the target.
    args = parser.parse_args(["doc.md"])
    assert _determine_output_format(args, Path("out.html")) == "html"


@pytest.mark.unit
def test_validation_outline_and_extract_mutually_exclusive() -> None:
    """Test validation catches when both --outline and --extract are used."""
    from all2md.cli.validation import ValidationSeverity, collect_argument_problems

    args = argparse.Namespace(outline=True, extract="#:1")

    problems = collect_argument_problems(args)

    assert len(problems) == 1
    assert problems[0].severity == ValidationSeverity.ERROR
    assert "--outline and --extract cannot be used together" in problems[0].message


@pytest.mark.unit
def test_validation_outline_only_no_error() -> None:
    """Test validation allows --outline when used alone."""
    from all2md.cli.validation import collect_argument_problems

    args = argparse.Namespace(outline=True, extract=None)

    problems = collect_argument_problems(args)

    # Filter to only outline/extract related problems
    outline_problems = [p for p in problems if "outline" in p.message.lower()]
    assert len(outline_problems) == 0


@pytest.mark.unit
def test_convert_single_file_with_outline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test convert_single_file handles outline mode correctly."""
    from all2md.ast.nodes import Document, Heading, Text
    from all2md.cli.input_items import CLIInputItem

    def fake_to_ast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[Text(content="Subtitle")]),
            ],
            metadata={},
        )

    monkeypatch.setattr(processors, "to_ast", fake_to_ast)
    monkeypatch.setattr(processors, "prepare_options_for_execution", lambda *args, **kwargs: {})

    input_path = tmp_path / "sample.md"
    input_path.write_text("# Title\n## Subtitle\n")

    input_item = CLIInputItem(
        raw_input=input_path,
        kind="local_file",
        display_name=input_path.name,
        path_hint=input_path,
    )

    exit_code, _, error = convert_single_file(
        input_item,
        output_path=None,
        options={},
        format_arg="markdown",
        transforms=None,
        show_progress=False,
        target_format="markdown",
        transform_specs=None,
        outline=True,
        outline_max_level=6,
    )

    assert exit_code == EXIT_SUCCESS
    assert error is None

    std = capsys.readouterr()
    assert "* Title" in std.out
    assert "  * Subtitle" in std.out


@pytest.mark.unit
def test_render_single_item_outline_with_rich(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test _render_single_item_to_stdout applies rich formatting to outline when requested."""
    pytest.importorskip("rich")

    from all2md.ast.nodes import Document, Heading, Text
    from all2md.cli.input_items import CLIInputItem

    def fake_to_ast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Main Title")]),
                Heading(level=2, content=[Text(content="Subsection")]),
            ],
            metadata={},
        )

    def fake_apply_rich_formatting(text: str, args: argparse.Namespace) -> tuple[str, bool]:
        # Simulate rich formatting by wrapping text
        return f"[RICH]{text}[/RICH]", True

    monkeypatch.setattr(processors, "to_ast", fake_to_ast)
    monkeypatch.setattr(processors, "prepare_options_for_execution", lambda *args, **kwargs: {})
    monkeypatch.setattr(processors, "_apply_rich_formatting", fake_apply_rich_formatting)

    input_path = tmp_path / "sample.md"
    input_path.write_text("# Main Title\n## Subsection\n")

    item = CLIInputItem(
        raw_input=input_path,
        kind="local_file",
        display_name=input_path.name,
        path_hint=input_path,
    )

    args = argparse.Namespace(
        outline=True,
        outline_max_level=6,
        pager=False,
    )

    exit_code = processors._render_single_item_to_stdout(
        item,
        args,
        options={},
        format_arg="markdown",
        transforms=None,
        should_use_rich=True,
        target_format="markdown",
    )

    assert exit_code == EXIT_SUCCESS

    std = capsys.readouterr()
    # Should contain rich-formatted content
    assert "[RICH]" in std.out
    assert "[/RICH]" in std.out
    assert "* Main Title" in std.out
    assert "  * Subsection" in std.out


def _args_for_near_source(**overrides: Any) -> argparse.Namespace:
    """Build a minimal args namespace for _near_source_attachment_options tests."""
    base = {
        "preserve_structure": True,
        "_provided_args": {"preserve_structure", "attachment_mode", "output_dir"},
    }
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.mark.unit
def test_near_source_attachments_injected_for_preserve_save(tmp_path):
    """Preserve-structure + save mode co-locates attachments beside the output file."""
    options = {"docx.attachment_mode": "save", "pdf.attachment_mode": "save"}
    output_path = tmp_path / "sub" / "report.md"

    updated = processors._near_source_attachment_options(options, output_path, _args_for_near_source())

    expected_dir = str(output_path.parent / ".attachments")
    assert updated["docx.attachment_output_dir"] == expected_dir
    assert updated["pdf.attachment_output_dir"] == expected_dir
    # Link base is relative to the markdown file so rendered links stay portable.
    assert updated["docx.attachment_base_url"] == ".attachments/"
    assert updated["pdf.attachment_base_url"] == ".attachments/"
    # Original dict is not mutated.
    assert "docx.attachment_output_dir" not in options


@pytest.mark.unit
def test_near_source_attachments_skipped_without_preserve(tmp_path):
    """Without --preserve-structure the options are returned unchanged."""
    options = {"docx.attachment_mode": "save"}
    args = _args_for_near_source(preserve_structure=False)
    result = processors._near_source_attachment_options(options, tmp_path / "report.md", args)
    assert result is options


@pytest.mark.unit
def test_near_source_attachments_skipped_when_not_save(tmp_path):
    """Non-save attachment modes never trigger near-source placement."""
    options = {"docx.attachment_mode": "base64"}
    result = processors._near_source_attachment_options(options, tmp_path / "report.md", _args_for_near_source())
    assert result is options


@pytest.mark.unit
def test_near_source_attachments_explicit_dir_wins(tmp_path):
    """An explicit --attachment-output-dir disables the near-source behavior."""
    options = {"docx.attachment_mode": "save"}
    args = _args_for_near_source(
        _provided_args={"preserve_structure", "attachment_mode", "output_dir", "attachment_output_dir"},
    )
    result = processors._near_source_attachment_options(options, tmp_path / "report.md", args)
    assert result is options


@pytest.mark.unit
def test_build_rich_theme_none_for_empty():
    """No styles means no theme override (keep Rich defaults)."""
    assert processors._build_rich_theme(None) is None
    assert processors._build_rich_theme({}) is None


@pytest.mark.unit
def test_build_rich_theme_prefixes_bare_markdown_keys():
    """Bare markdown element names are auto-prefixed with ``markdown.``."""
    pytest.importorskip("rich")

    theme = processors._build_rich_theme({"h1": "bold red", "block_quote": "italic green"})

    assert theme is not None
    assert "markdown.h1" in theme.styles
    assert "markdown.block_quote" in theme.styles


@pytest.mark.unit
def test_build_rich_theme_passes_dotted_keys_verbatim():
    """Fully-qualified style keys are passed to Rich unchanged."""
    pytest.importorskip("rich")

    theme = processors._build_rich_theme({"markdown.item.bullet": "yellow", "repr.number": "cyan"})

    assert theme is not None
    assert "markdown.item.bullet" in theme.styles
    assert "repr.number" in theme.styles


@pytest.mark.unit
def test_build_rich_theme_skips_invalid_styles():
    """Invalid style strings are dropped with a warning, valid ones kept."""
    pytest.importorskip("rich")
    from rich.style import Style
    from rich.theme import Theme

    theme = processors._build_rich_theme({"h1": "not a real style!!!", "h2": "bold"})

    # The valid h2 override is applied; the invalid h1 falls back to the Rich
    # default (i.e. it is NOT applied).
    assert theme is not None
    assert theme.styles["markdown.h2"] == Style.parse("bold")
    assert theme.styles["markdown.h1"] == Theme().styles["markdown.h1"]


@pytest.mark.unit
def test_build_rich_theme_ignores_non_string_values():
    """Non-string values are ignored rather than crashing."""
    pytest.importorskip("rich")
    from rich.style import Style
    from rich.theme import Theme

    theme = processors._build_rich_theme({"h1": 123, "h2": "bold"})

    # h1 (non-string) is ignored and keeps the Rich default; h2 is applied.
    assert theme is not None
    assert theme.styles["markdown.h2"] == Style.parse("bold")
    assert theme.styles["markdown.h1"] == Theme().styles["markdown.h1"]


@pytest.mark.unit
def test_apply_rich_formatting_passes_theme_to_console(monkeypatch: pytest.MonkeyPatch):
    """The stashed [rich] styles reach the Console as a Theme."""
    pytest.importorskip("rich")

    from all2md.cli.processors import _apply_rich_formatting

    captured_kwargs: dict[str, Any] = {}

    class DummyCapture:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def get(self):
            return "captured"

    class DummyConsole:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def print(self, _obj, *, no_wrap=None):
            pass

        def capture(self):
            return DummyCapture()

    class DummyMarkdown:
        def __init__(self, content, **_kwargs):
            self.content = content

    monkeypatch.setattr("rich.console.Console", DummyConsole)
    monkeypatch.setattr("rich.markdown.Markdown", DummyMarkdown)

    args = argparse.Namespace(rich_no_word_wrap=False, _rich_theme_styles={"h1": "bold red"})
    _text, is_rich = _apply_rich_formatting("data", args)

    assert is_rich is True
    theme = captured_kwargs.get("theme")
    assert theme is not None
    assert "markdown.h1" in theme.styles


@pytest.mark.unit
def test_load_converter_config_options_flattens_and_strips(tmp_path, monkeypatch):
    """Converter options come from the config; subcommand/[rich] tables are stripped."""
    cfg = tmp_path / ".all2md.toml"
    cfg.write_text(
        "attachment_mode = 'save'\n\n"
        "[pdf]\n"
        "detect_columns = true\n\n"
        "[view]\n"
        "dark = true\n\n"
        "[rich]\n"
        "h1 = 'bold red'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

    opts = processors.load_converter_config_options(explicit_path=str(cfg), no_config=False)

    assert opts.get("attachment_mode") == "save"
    assert opts.get("pdf.detect_columns") is True
    # [view] and [rich] are not converter options and must not leak through.
    assert not any(k == "dark" or k.startswith("view") for k in opts)
    assert not any(k.startswith("rich") or k == "h1" for k in opts)


@pytest.mark.unit
def test_load_converter_config_options_no_config_returns_empty(tmp_path, monkeypatch):
    """--no-config short-circuits config loading entirely."""
    cfg = tmp_path / ".all2md.toml"
    cfg.write_text("attachment_mode = 'save'\n", encoding="utf-8")
    monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

    assert processors.load_converter_config_options(explicit_path=str(cfg), no_config=True) == {}


@pytest.mark.unit
def test_page_content_emits_ansi_hint_on_windows_without_pager(monkeypatch, capsys):
    """On Windows with no PAGER, rich paging nudges the user toward an ANSI pager."""
    monkeypatch.delenv("PAGER", raising=False)
    monkeypatch.delenv("MANPAGER", raising=False)
    monkeypatch.setattr(processors.platform, "system", lambda: "Windows")
    paged: list[str] = []
    monkeypatch.setattr(processors.pydoc, "pager", lambda text: paged.append(text))

    assert processors._page_content("hello", is_rich=True) is True
    # Content is still paged (we no longer refuse), and a hint is printed to stderr.
    assert paged == ["hello"]
    assert "PAGER" in capsys.readouterr().err


@pytest.mark.unit
def test_page_content_no_hint_when_pager_configured(monkeypatch, capsys):
    """A configured PAGER suppresses the hint even for rich output on Windows."""
    monkeypatch.setenv("PAGER", "less -R")
    monkeypatch.setattr(processors.platform, "system", lambda: "Windows")
    monkeypatch.setattr(processors.pydoc, "pager", lambda text: None)

    assert processors._page_content("hello", is_rich=True) is True
    assert capsys.readouterr().err == ""


@pytest.mark.unit
def test_page_content_no_hint_for_plain_text(monkeypatch, capsys):
    """Plain-text paging never prints the ANSI hint, regardless of platform."""
    monkeypatch.delenv("PAGER", raising=False)
    monkeypatch.delenv("MANPAGER", raising=False)
    monkeypatch.setattr(processors.platform, "system", lambda: "Windows")
    monkeypatch.setattr(processors.pydoc, "pager", lambda text: None)

    assert processors._page_content("hello", is_rich=False) is True
    assert capsys.readouterr().err == ""

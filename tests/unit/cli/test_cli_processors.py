"""Unit tests for CLI processor utilities."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import Any

import pytest

from all2md.cli import processors
from all2md.cli.processors import (
    EXIT_SUCCESS,
    _should_use_rich_output,
    build_transform_instances,
    convert_single_file,
)
from all2md.converter_registry import registry
from all2md.exceptions import DependencyError


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
    monkeypatch.setattr('all2md.transforms.registry', stub_registry)
    monkeypatch.setattr('all2md.cli.processors.transform_registry', stub_registry)

    return {
        'metadata_instances': metadata_instances,
        'registry_instances': registry_instances,
        'transform_class': DummyTransform,
    }


@pytest.mark.unit
def test_build_transform_instances_records_transform_specs(dummy_transform_registry) -> None:
    """CLI transform builder should persist serializable transform specs."""
    args = argparse.Namespace(transforms=['demo-transform'], _provided_args=set())

    transforms = build_transform_instances(args)

    assert transforms is not None and len(transforms) == 1
    assert isinstance(transforms[0], dummy_transform_registry['transform_class'])
    assert dummy_transform_registry['metadata_instances']
    assert getattr(args, 'transform_specs', None) == [
        {'name': 'demo-transform', 'params': {}}
    ]


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
        captured['transforms'] = kwargs.get('transforms')
        # Return None to indicate success (content written to output)
        return None

    monkeypatch.setattr(processors, 'convert', fake_convert)
    monkeypatch.setattr(processors, 'prepare_options_for_execution', lambda *args, **kwargs: {})

    input_path = tmp_path / 'sample.pdf'
    input_path.write_text('stub')
    output_path = tmp_path / 'output.md'

    # Create CLIInputItem instead of using Path directly
    input_item = CLIInputItem(
        raw_input=input_path,
        kind='local_file',
        display_name=input_path.name,
        path_hint=input_path,
    )

    specs = [{'name': 'demo-transform', 'params': {}}]

    exit_code, _, error = convert_single_file(
        input_item,
        output_path,
        options={},
        format_arg='markdown',
        transforms=None,
        show_progress=False,
        target_format='markdown',
        transform_specs=specs,
    )

    assert exit_code == EXIT_SUCCESS, f"Expected EXIT_SUCCESS but got {exit_code}, error: {error}"
    assert error is None

    rebuilt = captured.get('transforms')
    assert rebuilt and len(rebuilt) == 1
    assert isinstance(rebuilt[0], dummy_transform_registry['transform_class'])


@pytest.mark.unit
def test_should_use_rich_output_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """_should_use_rich_output should raise DependencyError when rich is unavailable."""
    args = argparse.Namespace(rich=True, force_rich=False)
    monkeypatch.setattr(processors, '_check_rich_available', lambda: False)

    with pytest.raises(DependencyError) as exc:
        _should_use_rich_output(args)

    assert 'rich output requires the optional' in str(exc.value).lower()


@pytest.mark.unit
def test_registry_default_extension_uses_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry helper should respect metadata-provided extensions."""
    metadata = SimpleNamespace(extensions=['custom'])
    monkeypatch.setattr(registry, 'get_format_info', lambda name: [metadata])

    assert registry.get_default_extension_for_format('docx') == '.custom'


@pytest.mark.unit
def test_registry_default_extension_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry helper should fall back to .<format> when metadata is missing."""
    monkeypatch.setattr(registry, 'get_format_info', lambda name: None)

    assert registry.get_default_extension_for_format('pptx') == '.pptx'


@pytest.mark.unit
def test_apply_rich_formatting_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _apply_rich_formatting successfully renders markdown with Rich."""
    from all2md.cli.processors import _apply_rich_formatting
    import argparse

    args = argparse.Namespace(
        rich_code_theme='monokai',
        rich_inline_code_theme=None,
        rich_hyperlinks=True,
        rich_justify='left',
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
        def capture(self):
            return MockCapture()
        def print(self, *args, **kwargs):
            pass

    class MockMarkdown:
        def __init__(self, content, **kwargs):
            pass

    import sys
    mock_rich = type(sys)('rich')
    mock_rich.console = type(sys)('console')
    mock_rich.console.Console = MockConsole
    mock_rich.markdown = type(sys)('markdown')
    mock_rich.markdown.Markdown = MockMarkdown

    monkeypatch.setitem(sys.modules, 'rich', mock_rich)
    monkeypatch.setitem(sys.modules, 'rich.console', mock_rich.console)
    monkeypatch.setitem(sys.modules, 'rich.markdown', mock_rich.markdown)

    content, is_rich = _apply_rich_formatting(markdown, args)

    assert content == "RICH_RENDERED_CONTENT"
    assert is_rich is True


@pytest.mark.unit
def test_apply_rich_formatting_import_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Test _apply_rich_formatting handles ImportError gracefully."""
    from all2md.cli.processors import _apply_rich_formatting
    import argparse
    import sys

    args = argparse.Namespace()
    markdown = "# Test\nPlain markdown."

    # Remove rich from sys.modules to simulate ImportError
    for key in list(sys.modules.keys()):
        if key.startswith('rich'):
            monkeypatch.delitem(sys.modules, key, raising=False)

    # Prevent import of rich
    def import_blocker(name, *args, **kwargs):
        if name.startswith('rich'):
            raise ImportError(f"No module named '{name}'")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr('builtins.__import__', import_blocker)

    content, is_rich = _apply_rich_formatting(markdown, args)

    assert content == markdown  # Should return plain markdown
    assert is_rich is False

    # Check warning was printed
    captured = capsys.readouterr()
    assert "Rich library not installed" in captured.err

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
    monkeypatch.setattr('all2md.transforms.registry', stub_registry)

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
    captured: dict[str, Any] = {}

    def fake_convert(*_, transforms=None, **__):  # type: ignore[no-untyped-def]
        captured['transforms'] = transforms
        return None

    monkeypatch.setattr(processors, 'convert', fake_convert)
    monkeypatch.setattr(processors, 'prepare_options_for_execution', lambda *args, **kwargs: {})

    input_path = tmp_path / 'sample.pdf'
    input_path.write_text('stub')
    output_path = tmp_path / 'output.md'

    specs = [{'name': 'demo-transform', 'params': {}}]

    exit_code, _, error = convert_single_file(
        input_path,
        output_path,
        options={},
        format_arg='markdown',
        transforms=None,
        show_progress=False,
        target_format='markdown',
        transform_specs=specs,
    )

    assert exit_code == EXIT_SUCCESS
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

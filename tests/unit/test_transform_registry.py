#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for transform registry."""

import pytest

from all2md.ast.transforms import NodeTransformer
from all2md.transforms import ParameterSpec, TransformMetadata, TransformRegistry


class TransformA(NodeTransformer):
    """Test transform A."""
    pass


class TransformB(NodeTransformer):
    """Test transform B - depends on A."""
    pass


class TransformC(NodeTransformer):
    """Test transform C - depends on B."""
    pass


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reg = TransformRegistry()
    reg.clear()
    # Prevent auto-initialization from re-registering builtin transforms
    reg._initialized = True
    return reg


@pytest.fixture
def sample_metadata():
    """Create sample transform metadata."""
    return TransformMetadata(
        name="test-transform",
        description="Test transform",
        transformer_class=TransformA
    )


class TestTransformRegistry:
    """Tests for TransformRegistry class."""

    def test_singleton(self):
        """Test registry is a singleton."""
        reg1 = TransformRegistry()
        reg2 = TransformRegistry()
        assert reg1 is reg2

    def test_register_transform(self, registry, sample_metadata):
        """Test registering a transform."""
        registry.register(sample_metadata)

        assert registry.has_transform("test-transform")
        metadata = registry.get_metadata("test-transform")
        assert metadata.name == "test-transform"

    def test_register_duplicate_warning(self, registry, sample_metadata, caplog):
        """Test warning when registering duplicate transform."""
        registry.register(sample_metadata)
        registry.register(sample_metadata)  # Duplicate

        assert "already registered" in caplog.text.lower()

    def test_unregister_transform(self, registry, sample_metadata):
        """Test unregistering a transform."""
        registry.register(sample_metadata)
        assert registry.has_transform("test-transform")

        result = registry.unregister("test-transform")
        assert result is True
        assert not registry.has_transform("test-transform")

    def test_unregister_nonexistent(self, registry):
        """Test unregistering non-existent transform returns False."""
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_metadata_success(self, registry, sample_metadata):
        """Test getting metadata for registered transform."""
        registry.register(sample_metadata)
        metadata = registry.get_metadata("test-transform")
        assert metadata == sample_metadata

    def test_get_metadata_not_found(self, registry):
        """Test getting metadata for unregistered transform raises KeyError."""
        with pytest.raises(KeyError, match="not registered"):
            registry.get_metadata("nonexistent")

    def test_get_transform_no_params(self, registry):
        """Test getting transform instance without parameters."""
        metadata = TransformMetadata(
            name="simple",
            description="Simple transform",
            transformer_class=TransformA
        )
        registry.register(metadata)

        instance = registry.get_transform("simple")
        assert isinstance(instance, TransformA)

    def test_get_transform_with_params(self, registry):
        """Test getting transform instance with parameters."""
        class ParameterizedTransform(NodeTransformer):
            def __init__(self, value: int = 10):
                self.value = value

        metadata = TransformMetadata(
            name="parameterized",
            description="Parameterized transform",
            transformer_class=ParameterizedTransform,
            parameters={
                'value': ParameterSpec(type=int, default=10)
            }
        )
        registry.register(metadata)

        instance = registry.get_transform("parameterized", value=20)
        assert isinstance(instance, ParameterizedTransform)
        assert instance.value == 20

    def test_get_transform_invalid_params(self, registry):
        """Test getting transform with invalid parameters raises ValueError."""
        class ParameterizedTransform(NodeTransformer):
            def __init__(self, value: int = 10):
                self.value = value

        metadata = TransformMetadata(
            name="parameterized",
            description="Parameterized transform",
            transformer_class=ParameterizedTransform,
            parameters={
                'value': ParameterSpec(type=int, required=True)
            }
        )
        registry.register(metadata)

        with pytest.raises(ValueError):
            registry.get_transform("parameterized")  # Missing required param

    def test_has_transform(self, registry, sample_metadata):
        """Test checking if transform exists."""
        assert not registry.has_transform("test-transform")

        registry.register(sample_metadata)
        assert registry.has_transform("test-transform")

    def test_list_transforms_empty(self, registry):
        """Test listing transforms when none registered."""
        transforms = registry.list_transforms()
        assert transforms == []

    def test_list_transforms(self, registry):
        """Test listing all transforms."""
        metadata1 = TransformMetadata(
            name="transform-a",
            description="Transform A",
            transformer_class=TransformA
        )
        metadata2 = TransformMetadata(
            name="transform-b",
            description="Transform B",
            transformer_class=TransformB
        )

        registry.register(metadata1)
        registry.register(metadata2)

        transforms = registry.list_transforms()
        assert transforms == ["transform-a", "transform-b"]  # Sorted

    def test_list_transforms_with_tags(self, registry):
        """Test listing transforms filtered by tags."""
        metadata1 = TransformMetadata(
            name="transform-a",
            description="Transform A",
            transformer_class=TransformA,
            tags=["images", "cleanup"]
        )
        metadata2 = TransformMetadata(
            name="transform-b",
            description="Transform B",
            transformer_class=TransformB,
            tags=["text"]
        )
        metadata3 = TransformMetadata(
            name="transform-c",
            description="Transform C",
            transformer_class=TransformC,
            tags=["images"]
        )

        registry.register(metadata1)
        registry.register(metadata2)
        registry.register(metadata3)

        # Filter by 'images' tag
        image_transforms = registry.list_transforms(tags=["images"])
        assert set(image_transforms) == {"transform-a", "transform-c"}

    def test_resolve_dependencies_no_deps(self, registry):
        """Test dependency resolution with no dependencies."""
        metadata = TransformMetadata(
            name="simple",
            description="Simple transform",
            transformer_class=TransformA
        )
        registry.register(metadata)

        ordered = registry.resolve_dependencies(["simple"])
        assert ordered == ["simple"]

    def test_resolve_dependencies_linear(self, registry):
        """Test dependency resolution with linear dependencies."""
        # C depends on B, B depends on A
        metadata_a = TransformMetadata(
            name="a",
            description="Transform A",
            transformer_class=TransformA,
            priority=100
        )
        metadata_b = TransformMetadata(
            name="b",
            description="Transform B",
            transformer_class=TransformB,
            dependencies=["a"],
            priority=200
        )
        metadata_c = TransformMetadata(
            name="c",
            description="Transform C",
            transformer_class=TransformC,
            dependencies=["b"],
            priority=300
        )

        registry.register(metadata_a)
        registry.register(metadata_b)
        registry.register(metadata_c)

        # Request C - should get A, B, C in order
        ordered = registry.resolve_dependencies(["c"])
        assert ordered == ["a", "b", "c"]

    def test_resolve_dependencies_multiple(self, registry):
        """Test dependency resolution with multiple transforms."""
        metadata_a = TransformMetadata(
            name="a",
            description="Transform A",
            transformer_class=TransformA
        )
        metadata_b = TransformMetadata(
            name="b",
            description="Transform B",
            transformer_class=TransformB,
            dependencies=["a"]
        )
        metadata_c = TransformMetadata(
            name="c",
            description="Transform C",
            transformer_class=TransformC,
            dependencies=["a"]
        )

        registry.register(metadata_a)
        registry.register(metadata_b)
        registry.register(metadata_c)

        # Request B and C - both depend on A
        ordered = registry.resolve_dependencies(["b", "c"])
        assert ordered[0] == "a"  # A must be first
        assert set(ordered) == {"a", "b", "c"}

    def test_resolve_dependencies_missing(self, registry):
        """Test dependency resolution fails with missing dependency."""
        metadata = TransformMetadata(
            name="dependent",
            description="Depends on missing",
            transformer_class=TransformA,
            dependencies=["nonexistent"]
        )
        registry.register(metadata)

        with pytest.raises(ValueError, match="not found"):
            registry.resolve_dependencies(["dependent"])

    def test_resolve_dependencies_circular(self, registry):
        """Test dependency resolution fails with circular dependencies."""
        # A depends on B, B depends on A
        metadata_a = TransformMetadata(
            name="a",
            description="Transform A",
            transformer_class=TransformA,
            dependencies=["b"]
        )
        metadata_b = TransformMetadata(
            name="b",
            description="Transform B",
            transformer_class=TransformB,
            dependencies=["a"]
        )

        registry.register(metadata_a)
        registry.register(metadata_b)

        with pytest.raises(ValueError, match="Circular dependency"):
            registry.resolve_dependencies(["a"])

    def test_resolve_dependencies_priority(self, registry):
        """Test dependency resolution respects priority."""
        # No dependencies, but different priorities
        metadata_a = TransformMetadata(
            name="a",
            description="Transform A",
            transformer_class=TransformA,
            priority=200
        )
        metadata_b = TransformMetadata(
            name="b",
            description="Transform B",
            transformer_class=TransformB,
            priority=100
        )

        registry.register(metadata_a)
        registry.register(metadata_b)

        ordered = registry.resolve_dependencies(["a", "b"])
        assert ordered == ["b", "a"]  # B has lower priority, runs first

    def test_clear_registry(self, registry, sample_metadata):
        """Test clearing registry."""
        registry.register(sample_metadata)
        assert registry.has_transform("test-transform")

        registry.clear()
        registry._initialized = True  # Prevent re-initialization after clear
        assert not registry.has_transform("test-transform")
        assert registry.list_transforms() == []

    def test_discover_plugins_no_plugins(self, registry):
        """Test plugin discovery with no plugins."""
        # This tests the discovery mechanism doesn't crash
        count = registry.discover_plugins()
        assert isinstance(count, int)
        assert count >= 0  # May find built-in plugins or none

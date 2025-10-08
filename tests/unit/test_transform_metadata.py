#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for transform metadata classes."""

import pytest

from all2md.ast.transforms import NodeTransformer
from all2md.transforms import ParameterSpec, TransformMetadata


class DummyTransform(NodeTransformer):
    """Dummy transform for testing."""

    def __init__(self, threshold: int = 10, mode: str = "auto"):
        self.threshold = threshold
        self.mode = mode


class TestParameterSpec:
    """Tests for ParameterSpec class."""

    def test_basic_parameter(self):
        """Test basic parameter specification."""
        param = ParameterSpec(type=int, default=10, help="Threshold value")

        assert param.type is int
        assert param.default == 10
        assert param.help == "Threshold value"
        assert param.required is False
        assert param.choices is None

    def test_required_parameter(self):
        """Test required parameter."""
        param = ParameterSpec(type=str, required=True, help="Required string")

        assert param.required is True
        assert param.default is None

    def test_parameter_with_choices(self):
        """Test parameter with choices."""
        param = ParameterSpec(
            type=str,
            default="auto",
            choices=["auto", "manual", "disabled"],
            help="Mode"
        )

        assert param.choices == ["auto", "manual", "disabled"]
        assert param.validate("auto") is True

    def test_validate_type_success(self):
        """Test type validation - success case."""
        param = ParameterSpec(type=int, default=10)
        assert param.validate(20) is True

    def test_validate_type_failure(self):
        """Test type validation - failure case."""
        param = ParameterSpec(type=int, default=10)

        with pytest.raises(ValueError, match="Expected type int"):
            param.validate("not an int")

    def test_validate_choices_success(self):
        """Test choices validation - success case."""
        param = ParameterSpec(type=str, choices=["a", "b", "c"])
        assert param.validate("b") is True

    def test_validate_choices_failure(self):
        """Test choices validation - failure case."""
        param = ParameterSpec(type=str, choices=["a", "b", "c"])

        with pytest.raises(ValueError, match="must be one of"):
            param.validate("d")

    def test_custom_validator_success(self):
        """Test custom validator - success case."""
        def positive(value):
            if value <= 0:
                raise ValueError("Must be positive")
            return True

        param = ParameterSpec(type=int, validator=positive)
        assert param.validate(10) is True

    def test_custom_validator_failure(self):
        """Test custom validator - failure case."""
        def positive(value):
            if value <= 0:
                raise ValueError("Must be positive")
            return True

        param = ParameterSpec(type=int, validator=positive)

        with pytest.raises(ValueError, match="Must be positive"):
            param.validate(-5)

    def test_get_cli_flag_auto(self):
        """Test automatic CLI flag generation."""
        param = ParameterSpec(type=int)
        assert param.get_cli_flag("threshold") == "--threshold"
        assert param.get_cli_flag("max_value") == "--max-value"

    def test_get_cli_flag_custom(self):
        """Test custom CLI flag."""
        param = ParameterSpec(type=int, cli_flag="--custom")
        assert param.get_cli_flag("threshold") == "--custom"


class TestTransformMetadata:
    """Tests for TransformMetadata class."""

    def test_basic_metadata(self):
        """Test basic metadata creation."""
        metadata = TransformMetadata(
            name="test-transform",
            description="Test transform",
            transformer_class=DummyTransform
        )

        assert metadata.name == "test-transform"
        assert metadata.description == "Test transform"
        assert metadata.transformer_class == DummyTransform
        assert metadata.parameters == {}
        assert metadata.priority == 100
        assert metadata.dependencies == []

    def test_metadata_with_parameters(self):
        """Test metadata with parameters."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            parameters={
                'threshold': ParameterSpec(type=int, default=10),
                'mode': ParameterSpec(type=str, default="auto")
            }
        )

        assert len(metadata.parameters) == 2
        assert 'threshold' in metadata.parameters
        assert 'mode' in metadata.parameters

    def test_metadata_with_dependencies(self):
        """Test metadata with dependencies."""
        metadata = TransformMetadata(
            name="dependent",
            description="Depends on others",
            transformer_class=DummyTransform,
            dependencies=["base-transform", "util-transform"],
            priority=200
        )

        assert metadata.dependencies == ["base-transform", "util-transform"]
        assert metadata.priority == 200

    def test_metadata_validation_empty_name(self):
        """Test validation fails with empty name."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            TransformMetadata(
                name="",
                description="Test",
                transformer_class=DummyTransform
            )

    def test_metadata_validation_wrong_class(self):
        """Test validation fails with non-NodeTransformer class."""
        class NotATransformer:
            pass

        with pytest.raises(ValueError, match="must inherit from NodeTransformer"):
            TransformMetadata(
                name="invalid",
                description="Invalid",
                transformer_class=NotATransformer  # type: ignore
            )

    def test_metadata_validation_negative_priority(self):
        """Test validation fails with negative priority."""
        with pytest.raises(ValueError, match="must be non-negative"):
            TransformMetadata(
                name="test",
                description="Test",
                transformer_class=DummyTransform,
                priority=-1
            )

    def test_create_instance_no_params(self):
        """Test creating transform instance without parameters."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform
        )

        instance = metadata.create_instance()
        assert isinstance(instance, DummyTransform)
        assert instance.threshold == 10  # default
        assert instance.mode == "auto"  # default

    def test_create_instance_with_params(self):
        """Test creating transform instance with parameters."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            parameters={
                'threshold': ParameterSpec(type=int, default=10),
                'mode': ParameterSpec(type=str, default="auto")
            }
        )

        instance = metadata.create_instance(threshold=20, mode="manual")
        assert isinstance(instance, DummyTransform)
        assert instance.threshold == 20
        assert instance.mode == "manual"

    def test_create_instance_missing_required(self):
        """Test creating instance fails with missing required parameter."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            parameters={
                'threshold': ParameterSpec(type=int, required=True)
            }
        )

        with pytest.raises(ValueError, match="Required parameter"):
            metadata.create_instance()

    def test_create_instance_invalid_value(self):
        """Test creating instance fails with invalid parameter value."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            parameters={
                'threshold': ParameterSpec(type=int, choices=[5, 10, 15])
            }
        )

        with pytest.raises(ValueError, match="must be one of"):
            metadata.create_instance(threshold=20)

    def test_get_parameter_names(self):
        """Test getting parameter names."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            parameters={
                'threshold': ParameterSpec(type=int),
                'mode': ParameterSpec(type=str)
            }
        )

        names = metadata.get_parameter_names()
        assert set(names) == {'threshold', 'mode'}

    def test_has_parameter(self):
        """Test checking for parameter existence."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            parameters={
                'threshold': ParameterSpec(type=int)
            }
        )

        assert metadata.has_parameter('threshold') is True
        assert metadata.has_parameter('nonexistent') is False

    def test_metadata_with_tags(self):
        """Test metadata with tags."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            tags=["images", "cleanup"]
        )

        assert metadata.tags == ["images", "cleanup"]

    def test_metadata_with_author(self):
        """Test metadata with author."""
        metadata = TransformMetadata(
            name="test",
            description="Test",
            transformer_class=DummyTransform,
            version="2.1.0",
            author="Test Author"
        )

        assert metadata.version == "2.1.0"
        assert metadata.author == "Test Author"

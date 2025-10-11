#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/metadata.py
"""Metadata classes for AST transforms.

This module defines metadata structures for transform registration and discovery.
Transform metadata enables CLI argument generation, validation, and plugin discovery
through entry points.

Examples
--------
Define a transform with metadata:

    >>> from all2md.transforms import TransformMetadata, ParameterSpec
    >>> from all2md.ast.transforms import NodeTransformer
    >>>
    >>> class MyTransform(NodeTransformer):
    ...     def __init__(self, threshold: int = 10):
    ...         self.threshold = threshold
    ...
    >>> METADATA = TransformMetadata(
    ...     name="my-transform",
    ...     description="Example transform",
    ...     transformer_class=MyTransform,
    ...     parameters={
    ...         'threshold': ParameterSpec(
    ...             type=int,
    ...             default=10,
    ...             help="Threshold value"
    ...         )
    ...     }
    ... )

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from all2md.ast.transforms import NodeTransformer


@dataclass
class ParameterSpec:
    """Specification for a transform parameter.

    This class describes a single parameter accepted by a transform, including
    type information, default values, and metadata for CLI generation.

    Parameters
    ----------
    type : type
        Python type of the parameter (e.g., int, str, bool)
    default : Any, optional
        Default value if parameter is not provided
    help : str, optional
        Help text describing the parameter (used in CLI --help)
    cli_flag : str, optional
        Custom CLI flag name (e.g., '--my-param'). If None, auto-generated
        from parameter name
    required : bool, default = False
        Whether this parameter is required
    choices : list, optional
        List of valid choices for this parameter
    validator : callable, optional
        Custom validation function: takes value, returns bool or raises ValueError
    element_type : type, optional
        For list parameters, the expected type of list elements (e.g., str, int)

    Examples
    --------
    Simple parameter:
        >>> param = ParameterSpec(type=int, default=10, help="Threshold value")

    Parameter with choices:
        >>> param = ParameterSpec(
        ...     type=str,
        ...     default="auto",
        ...     choices=["auto", "manual", "disabled"],
        ...     help="Processing mode"
        ... )

    Required parameter with validation:
        >>> def validate_positive(value):
        ...     if value <= 0:
        ...         raise ValueError("Must be positive")
        ...     return True
        >>> param = ParameterSpec(
        ...     type=int,
        ...     required=True,
        ...     validator=validate_positive,
        ...     help="Positive integer"
        ... )

    List parameter with element type validation:
        >>> param = ParameterSpec(
        ...     type=list,
        ...     element_type=str,
        ...     default=["image", "table"],
        ...     help="Node types to remove"
        ... )

    """

    type: Type
    default: Any = None
    help: str = ""
    cli_flag: Optional[str] = None
    required: bool = False
    choices: Optional[list[Any]] = None
    validator: Optional[Callable[[Any], bool]] = None
    element_type: Optional[Type] = None

    def validate(self, value: Any) -> bool:
        """Validate a parameter value.

        Parameters
        ----------
        value : Any
            Value to validate

        Returns
        -------
        bool
            True if valid

        Raises
        ------
        ValueError
            If value is invalid

        """
        # Check type
        if not isinstance(value, self.type):
            raise ValueError(f"Expected type {self.type.__name__}, got {type(value).__name__}")

        # Check list element types
        if self.type is list and self.element_type is not None:
            if not isinstance(value, list):
                raise ValueError(f"Expected list, got {type(value).__name__}")
            for i, element in enumerate(value):
                if not isinstance(element, self.element_type):
                    raise ValueError(
                        f"List element at index {i} has wrong type: "
                        f"expected {self.element_type.__name__}, got {type(element).__name__}"
                    )

        # Check choices
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"Value must be one of {self.choices}, got {value}")

        # Run custom validator
        if self.validator is not None:
            if not self.validator(value):
                raise ValueError(f"Validation failed for value: {value}")

        return True

    def get_cli_flag(self, param_name: str) -> str:
        """Get CLI flag name for this parameter.

        Parameters
        ----------
        param_name : str
            Parameter name from the transform

        Returns
        -------
        str
            CLI flag (e.g., '--threshold')

        """
        if self.cli_flag:
            return self.cli_flag

        # Auto-generate: convert snake_case to kebab-case
        flag_name = param_name.replace('_', '-')
        return f'--{flag_name}'


@dataclass
class TransformMetadata:
    """Metadata for a transform.

    This class describes a transform for registration, discovery, and CLI integration.
    It follows the same pattern as `ConverterMetadata` for consistency.

    Parameters
    ----------
    name : str
        Unique identifier for the transform (e.g., "remove-images")
    description : str
        Human-readable description of what the transform does
    transformer_class : type[NodeTransformer]
        The transform class (must inherit from NodeTransformer)
    parameters : dict[str, ParameterSpec], default = empty dict
        Parameters accepted by the transform constructor
    priority : int, default = 100
        Execution priority (lower runs first). Used for dependency ordering
    dependencies : list[str], default = empty list
        Names of transforms that must run before this one
    version : str, default = "1.0.0"
        Transform version (semantic versioning)
    author : str, optional
        Transform author or maintainer
    tags : list[str], default = empty list
        Tags for categorization (e.g., ["images", "cleanup"])

    Examples
    --------
    Basic transform metadata:
        >>> metadata = TransformMetadata(
        ...     name="remove-images",
        ...     description="Remove all image nodes from the AST",
        ...     transformer_class=RemoveImagesTransform
        ... )

    Transform with parameters:
        >>> metadata = TransformMetadata(
        ...     name="heading-offset",
        ...     description="Shift heading levels by an offset",
        ...     transformer_class=HeadingOffsetTransform,
        ...     parameters={
        ...         'offset': ParameterSpec(
        ...             type=int,
        ...             default=1,
        ...             help="Number of levels to shift (positive or negative)"
        ...         )
        ...     }
        ... )

    Transform with dependencies:
        >>> metadata = TransformMetadata(
        ...     name="sanitize-links",
        ...     description="Sanitize and validate all links",
        ...     transformer_class=SanitizeLinksTransform,
        ...     dependencies=["extract-metadata"],
        ...     priority=200
        ... )

    """

    name: str
    description: str
    transformer_class: Type[NodeTransformer]
    parameters: dict[str, ParameterSpec] = field(default_factory=dict)
    priority: int = 100
    dependencies: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        # Validate name
        if not self.name:
            raise ValueError("Transform name cannot be empty")

        # Validate transformer_class
        if not issubclass(self.transformer_class, NodeTransformer):
            raise ValueError(
                f"transformer_class must inherit from NodeTransformer, "
                f"got {self.transformer_class.__name__}"
            )

        # Validate priority
        if self.priority < 0:
            raise ValueError(f"Priority must be non-negative, got {self.priority}")

    def create_instance(self, **kwargs: Any) -> NodeTransformer:
        """Create an instance of the transform with given parameters.

        Parameters
        ----------
        **kwargs
            Parameters to pass to the transform constructor

        Returns
        -------
        NodeTransformer
            Transform instance

        Raises
        ------
        ValueError
            If required parameters are missing or validation fails

        Examples
        --------
        >>> metadata = TransformMetadata(
        ...     name="test",
        ...     description="Test transform",
        ...     transformer_class=MyTransform,
        ...     parameters={'threshold': ParameterSpec(type=int, default=10)}
        ... )
        >>> instance = metadata.create_instance(threshold=20)

        """
        # Validate and filter parameters
        validated_params = {}

        for param_name, param_spec in self.parameters.items():
            if param_name in kwargs:
                # Validate provided value
                value = kwargs[param_name]
                param_spec.validate(value)
                validated_params[param_name] = value
            elif param_spec.required:
                raise ValueError(f"Required parameter '{param_name}' not provided")
            elif param_spec.default is not None:
                validated_params[param_name] = param_spec.default

        # Create instance
        try:
            return self.transformer_class(**validated_params)
        except TypeError as e:
            raise ValueError(f"Failed to create transform instance: {e}") from e

    def get_parameter_names(self) -> list[str]:
        """Get list of parameter names.

        Returns
        -------
        list[str]
            Parameter names

        """
        return list(self.parameters.keys())

    def has_parameter(self, name: str) -> bool:
        """Check if transform has a parameter.

        Parameters
        ----------
        name : str
            Parameter name

        Returns
        -------
        bool
            True if parameter exists

        """
        return name in self.parameters


__all__ = [
    "ParameterSpec",
    "TransformMetadata",
]

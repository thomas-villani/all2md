#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/openapi.py
"""Options for OpenAPI/Swagger parsing.

This module provides configuration options for parsing OpenAPI/Swagger
specification documents (versions 2.0 and 3.x).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_OPENAPI_CODE_BLOCK_LANGUAGE,
    DEFAULT_OPENAPI_EXPAND_REFS,
    DEFAULT_OPENAPI_GROUP_BY_TAG,
    DEFAULT_OPENAPI_INCLUDE_DEPRECATED,
    DEFAULT_OPENAPI_INCLUDE_EXAMPLES,
    DEFAULT_OPENAPI_INCLUDE_SCHEMAS,
    DEFAULT_OPENAPI_INCLUDE_SERVERS,
    DEFAULT_OPENAPI_MAX_SCHEMA_DEPTH,
    DEFAULT_OPENAPI_VALIDATE_SPEC,
)
from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class OpenApiParserOptions(BaseParserOptions):
    """Options for parsing OpenAPI/Swagger specification documents.

    This dataclass contains settings specific to parsing OpenAPI specifications
    into AST representation, supporting both OpenAPI 3.x and Swagger 2.0 formats.

    Parameters
    ----------
    include_servers : bool, default = True
        Whether to include server information section
    include_schemas : bool, default = True
        Whether to include schema/model definitions section
    include_examples : bool, default = True
        Whether to include request/response examples as code blocks
    group_by_tag : bool, default = True
        Whether to group API paths by tags. When True, paths are organized
        under tag headings. When False, paths are listed sequentially.
    max_schema_depth : int, default = 3
        Maximum nesting depth for rendering schema properties. Prevents
        infinite recursion in circular schemas.
    code_block_language : str, default = "json"
        Language identifier for code block examples (json, yaml, etc.)
    validate_spec : bool, default = False
        Whether to validate the OpenAPI spec using jsonschema (requires
        jsonschema package). When True, raises ParsingError for invalid specs.
    include_deprecated : bool, default = True
        Whether to include deprecated operations and parameters
    expand_refs : bool, default = True
        Whether to expand $ref references inline or keep them as links

    Examples
    --------
    Parse with minimal output:
        >>> options = OpenApiParserOptions(
        ...     include_servers=False,
        ...     include_schemas=False
        ... )

    Validate spec during parsing:
        >>> options = OpenApiParserOptions(validate_spec=True)

    """

    include_servers: bool = field(
        default=DEFAULT_OPENAPI_INCLUDE_SERVERS,
        metadata={
            "help": "Include server information section",
            "cli_name": "no-include-servers",
            "importance": "core",
        },
    )
    include_schemas: bool = field(
        default=DEFAULT_OPENAPI_INCLUDE_SCHEMAS,
        metadata={
            "help": "Include schema/model definitions section",
            "cli_name": "no-include-schemas",
            "importance": "core",
        },
    )
    include_examples: bool = field(
        default=DEFAULT_OPENAPI_INCLUDE_EXAMPLES,
        metadata={
            "help": "Include request/response examples as code blocks",
            "cli_name": "no-include-examples",
            "importance": "core",
        },
    )
    group_by_tag: bool = field(
        default=DEFAULT_OPENAPI_GROUP_BY_TAG,
        metadata={
            "help": "Group API paths by tags",
            "cli_name": "no-group-by-tag",
            "importance": "core",
        },
    )

    max_schema_depth: int = field(
        default=DEFAULT_OPENAPI_MAX_SCHEMA_DEPTH,
        metadata={
            "help": "Maximum nesting depth for schema properties (prevents circular refs)",
            "type": int,
            "importance": "advanced",
        },
    )
    code_block_language: str = field(
        default=DEFAULT_OPENAPI_CODE_BLOCK_LANGUAGE,
        metadata={
            "help": "Language identifier for code block examples",
            "choices": ["json", "yaml", "text"],
            "importance": "advanced",
        },
    )
    validate_spec: bool = field(
        default=DEFAULT_OPENAPI_VALIDATE_SPEC,
        metadata={
            "help": "Validate OpenAPI spec",
            "importance": "advanced",
        },
    )
    include_deprecated: bool = field(
        default=DEFAULT_OPENAPI_INCLUDE_DEPRECATED,
        metadata={
            "help": "Include deprecated operations and parameters",
            "cli_name": "no-include-deprecated",
            "importance": "core",
        },
    )
    expand_refs: bool = field(
        default=DEFAULT_OPENAPI_EXPAND_REFS,
        metadata={
            "help": "Expand $ref references inline or keep as links",
            "cli_name": "no-expand-refs",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for OpenAPI options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate max_schema_depth
        if self.max_schema_depth < 1:
            raise ValueError(f"max_schema_depth must be at least 1, got {self.max_schema_depth}")

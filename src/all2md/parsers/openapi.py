#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/openapi.py
"""OpenAPI/Swagger to AST converter.

This module provides conversion from OpenAPI/Swagger specification documents
to AST representation. Supports OpenAPI 3.x and Swagger 2.0 formats.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.constants import DEPS_OPENAPI
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.openapi import OpenApiParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.encoding import read_text_with_encoding_detection
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _validate_openapi_structure(data: dict[str, Any]) -> bool:
    """Validate if a parsed dictionary is a valid OpenAPI/Swagger spec.

    Parameters
    ----------
    data : dict
        Parsed specification data

    Returns
    -------
    bool
        True if data is a valid OpenAPI/Swagger spec

    """
    # Check for OpenAPI 3.x
    if "openapi" in data and "paths" in data and "info" in data:
        openapi_version = data["openapi"]
        if isinstance(openapi_version, (str, float, int)):
            openapi_str = str(openapi_version)
            if openapi_str.startswith("3."):
                if isinstance(data["paths"], dict):
                    if isinstance(data["info"], dict) and "title" in data["info"]:
                        return True

    # Check for Swagger 2.0
    if "swagger" in data and "paths" in data and "info" in data:
        swagger_version = data["swagger"]
        if isinstance(swagger_version, (str, float, int)):
            swagger_str = str(swagger_version)
            if swagger_str.startswith("2."):
                if isinstance(data["paths"], dict):
                    if isinstance(data["info"], dict) and "title" in data["info"]:
                        return True

    return False


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Attempt to parse text as JSON.

    Parameters
    ----------
    text : str
        Text to parse

    Returns
    -------
    dict or None
        Parsed dict if successful, None otherwise

    """
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return None


def _try_parse_yaml(text: str) -> dict[str, Any] | None:
    """Attempt to parse text as YAML.

    Parameters
    ----------
    text : str
        Text to parse

    Returns
    -------
    dict or None
        Parsed dict if successful, None otherwise

    """
    try:
        import yaml

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _is_openapi_content(content: bytes) -> bool:
    """Detect if content is an OpenAPI/Swagger specification.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be OpenAPI/Swagger spec

    """
    try:
        # Try to decode as text
        text = content.decode("utf-8", errors="ignore")

        # Quick check for OpenAPI/Swagger keywords
        if "openapi" not in text and "swagger" not in text:
            return False

        # Try parsing as JSON first
        data = _try_parse_json(text)
        if data and _validate_openapi_structure(data):
            return True

        # Try parsing as YAML
        data = _try_parse_yaml(text)
        if data and _validate_openapi_structure(data):
            return True

        return False

    except UnicodeDecodeError:
        return False


class OpenApiParser(BaseParser):
    """Convert OpenAPI/Swagger specifications to AST representation.

    This parser handles OpenAPI 3.x and Swagger 2.0 specification formats,
    converting them into structured markdown-ready AST.

    Parameters
    ----------
    options : OpenApiParserOptions or None
        Parser configuration options
    progress_callback : ProgressCallback or None
        Optional callback for progress updates

    Examples
    --------
    Parse OpenAPI spec:
        >>> parser = OpenApiParser()
        >>> doc = parser.parse("openapi.yaml")

    With custom options:
        >>> options = OpenApiParserOptions(group_by_tag=False)
        >>> parser = OpenApiParser(options)
        >>> doc = parser.parse("swagger.json")

    """

    def __init__(
        self, options: OpenApiParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the OpenAPI parser with options and progress callback."""
        BaseParser._validate_options_type(options, OpenApiParserOptions, "openapi")
        options = options or OpenApiParserOptions()
        super().__init__(options or OpenApiParserOptions(), progress_callback)
        self.options: OpenApiParserOptions = options or OpenApiParserOptions()

    @requires_dependencies("openapi", DEPS_OPENAPI)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse OpenAPI/Swagger specification into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input OpenAPI specification to parse

        Returns
        -------
        Document
            AST Document node representing the parsed API specification

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format or structure

        """
        self._emit_progress("started", "Parsing OpenAPI specification", total=1)

        try:
            # Load spec content
            spec = self._load_spec(input_data)

            # Validate if requested
            if self.options.validate_spec:
                self._validate_spec(spec)

            # Extract metadata
            metadata = self.extract_metadata(spec)

            # Build AST
            children: list[Node] = []

            # Add title and description
            children.extend(self._build_info_section(spec))

            # Add servers section
            if self.options.include_servers:
                children.extend(self._build_servers_section(spec))

            # Add paths section
            children.extend(self._build_paths_section(spec))

            # Add schemas section
            if self.options.include_schemas:
                children.extend(self._build_schemas_section(spec))

            self._emit_progress("finished", "OpenAPI parsing complete", current=1, total=1)

            return Document(children=children, metadata=metadata.to_dict())

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(
                f"Failed to parse OpenAPI specification: {e}", parsing_stage="openapi_parsing", original_error=e
            ) from e

    def _load_spec(self, input_data: Union[str, Path, IO[bytes], bytes]) -> dict[str, Any]:
        """Load OpenAPI spec from various input types.

        Parameters
        ----------
        input_data : various
            Input data to load

        Returns
        -------
        dict
            Parsed OpenAPI specification

        Raises
        ------
        ParsingError
            If spec cannot be loaded or parsed

        """
        # Read content
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            # Check if it's an existing file before trying to open
            # This allows passing inline YAML/JSON strings
            if path.exists():
                with open(path, "rb") as f:
                    content = f.read()
            else:
                # Treat as inline YAML/JSON content
                if isinstance(input_data, str):
                    content = input_data.encode("utf-8")
                else:
                    # Path object that doesn't exist - treat as string content
                    content = str(input_data).encode("utf-8")
        elif isinstance(input_data, bytes):
            content = input_data
        else:
            # File-like object
            raw_content: bytes | str = input_data.read()
            if isinstance(raw_content, str):
                content = raw_content.encode("utf-8")
            else:
                content = raw_content

        # Decode to text
        text = read_text_with_encoding_detection(content)

        # Try JSON first
        try:
            spec = json.loads(text)
            logger.debug("Loaded OpenAPI spec as JSON")
            return spec
        except json.JSONDecodeError:
            pass

        # Try YAML
        try:
            import yaml

            spec = yaml.safe_load(text)
            logger.debug("Loaded OpenAPI spec as YAML")
            if not isinstance(spec, dict):
                raise ParsingError("OpenAPI spec must be a dictionary/object", parsing_stage="spec_loading")
            return spec
        except Exception as e:
            raise ParsingError(
                f"Failed to parse OpenAPI spec as JSON or YAML: {e}", parsing_stage="spec_loading", original_error=e
            ) from e

    def _validate_spec(self, spec: dict[str, Any]) -> None:
        """Validate OpenAPI spec structure.

        Parameters
        ----------
        spec : dict
            OpenAPI specification to validate

        Raises
        ------
        ParsingError
            If validation fails

        """
        # Basic validation - check required fields
        if "openapi" in spec:
            # OpenAPI 3.x
            if not spec.get("info"):
                raise ParsingError("OpenAPI spec missing required 'info' section", parsing_stage="validation")
            if not spec.get("paths"):
                raise ParsingError("OpenAPI spec missing required 'paths' section", parsing_stage="validation")
        elif "swagger" in spec:
            # Swagger 2.0
            if not spec.get("info"):
                raise ParsingError("Swagger spec missing required 'info' section", parsing_stage="validation")
            if not spec.get("paths"):
                raise ParsingError("Swagger spec missing required 'paths' section", parsing_stage="validation")
        else:
            raise ParsingError("Spec must have 'openapi' or 'swagger' version field", parsing_stage="validation")

    def _build_info_section(self, spec: dict[str, Any]) -> list[Node]:
        """Build info section with title, version, description.

        Parameters
        ----------
        spec : dict
            OpenAPI specification

        Returns
        -------
        list of Node
            AST nodes for info section

        """
        nodes: list[Node] = []
        info = spec.get("info", {})

        # Title
        title = info.get("title", "API Documentation")
        nodes.append(Heading(level=1, content=[Text(content=title)]))

        # Description
        description = info.get("description")
        if description:
            nodes.append(Paragraph(content=[Text(content=description)]))

        # Version and other info as table
        table_data = []
        if "version" in info:
            table_data.append(["Version", str(info["version"])])
        if "termsOfService" in info:
            table_data.append(["Terms of Service", str(info["termsOfService"])])

        # Contact info
        if "contact" in info:
            contact = info["contact"]
            if "name" in contact:
                table_data.append(["Contact", contact["name"]])
            if "email" in contact:
                table_data.append(["Email", contact["email"]])
            if "url" in contact:
                table_data.append(["Contact URL", contact["url"]])

        # License info
        if "license" in info:
            license_info = info["license"]
            if "name" in license_info:
                license_str = license_info["name"]
                if "url" in license_info:
                    license_str += f" ({license_info['url']})"
                table_data.append(["License", license_str])

        if table_data:
            header_row = TableRow(
                cells=[
                    TableCell(content=[Text(content="Field")], alignment="left"),
                    TableCell(content=[Text(content="Value")], alignment="left"),
                ],
                is_header=True,
            )
            data_rows = [
                TableRow(
                    cells=[
                        TableCell(content=[Text(content=field)], alignment="left"),
                        TableCell(content=[Text(content=value)], alignment="left"),
                    ],
                    is_header=False,
                )
                for field, value in table_data
            ]
            nodes.append(Table(header=header_row, rows=data_rows, alignments=["left", "left"]))

        return nodes

    def _build_servers_section(self, spec: dict[str, Any]) -> list[Node]:
        """Build servers section.

        Parameters
        ----------
        spec : dict
            OpenAPI specification

        Returns
        -------
        list of Node
            AST nodes for servers section

        """
        nodes: list[Node] = []

        # OpenAPI 3.x servers
        servers = spec.get("servers", [])
        if servers:
            nodes.append(Heading(level=2, content=[Text(content="Servers")]))

            server_rows = []
            for server in servers:
                url = server.get("url", "")
                description = server.get("description", "")
                server_rows.append([url, description])

            if server_rows:
                header_row = TableRow(
                    cells=[
                        TableCell(content=[Text(content="URL")], alignment="left"),
                        TableCell(content=[Text(content="Description")], alignment="left"),
                    ],
                    is_header=True,
                )
                data_rows = [
                    TableRow(
                        cells=[
                            TableCell(content=[Text(content=url)], alignment="left"),
                            TableCell(content=[Text(content=desc)], alignment="left"),
                        ],
                        is_header=False,
                    )
                    for url, desc in server_rows
                ]
                nodes.append(Table(header=header_row, rows=data_rows, alignments=["left", "left"]))

        # Swagger 2.0 host/basePath
        elif "host" in spec or "basePath" in spec:
            nodes.append(Heading(level=2, content=[Text(content="Base URL")]))
            host = spec.get("host", "")
            base_path = spec.get("basePath", "")
            schemes = spec.get("schemes", ["http"])
            for scheme in schemes:
                url = f"{scheme}://{host}{base_path}"
                nodes.append(Paragraph(content=[Text(content=url)]))

        return nodes

    def _build_paths_section(self, spec: dict[str, Any]) -> list[Node]:
        """Build paths/endpoints section.

        Parameters
        ----------
        spec : dict
            OpenAPI specification

        Returns
        -------
        list of Node
            AST nodes for paths section

        """
        nodes: list[Node] = []
        paths = spec.get("paths", {})

        if not paths:
            return nodes

        nodes.append(Heading(level=2, content=[Text(content="API Endpoints")]))

        if self.options.group_by_tag:
            # Group by tags
            tags_data: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
            untagged: list[tuple[str, str, dict[str, Any]]] = []

            for path, path_item in paths.items():
                for method, operation in path_item.items():
                    if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"]:
                        continue
                    if not isinstance(operation, dict):
                        continue

                    # Check if deprecated and should be excluded
                    if operation.get("deprecated") and not self.options.include_deprecated:
                        continue

                    tags = operation.get("tags", [])
                    if tags:
                        for tag in tags:
                            if tag not in tags_data:
                                tags_data[tag] = []
                            tags_data[tag].append((path, method.upper(), operation))
                    else:
                        untagged.append((path, method.upper(), operation))

            # Render tagged operations
            for tag, operations in sorted(tags_data.items()):
                nodes.append(Heading(level=3, content=[Text(content=tag)]))
                for path, method, operation in operations:
                    nodes.extend(self._build_operation(path, method, operation))

            # Render untagged operations
            if untagged:
                nodes.append(Heading(level=3, content=[Text(content="Other")]))
                for path, method, operation in untagged:
                    nodes.extend(self._build_operation(path, method, operation))

        else:
            # List sequentially
            for path, path_item in paths.items():
                for method, operation in path_item.items():
                    if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"]:
                        continue
                    if not isinstance(operation, dict):
                        continue

                    # Check if deprecated and should be excluded
                    if operation.get("deprecated") and not self.options.include_deprecated:
                        continue

                    nodes.extend(self._build_operation(path, method.upper(), operation))

        return nodes

    def _build_operation(self, path: str, method: str, operation: dict[str, Any]) -> list[Node]:
        """Build AST for a single API operation.

        Parameters
        ----------
        path : str
            API path (e.g., /users/{id})
        method : str
            HTTP method (GET, POST, etc.)
        operation : dict
            Operation object from spec

        Returns
        -------
        list of Node
            AST nodes for operation

        """
        nodes: list[Node] = []

        # Operation heading
        summary = operation.get("summary", operation.get("operationId", ""))
        heading_text = f"{method} {path}"
        if summary:
            heading_text += f" - {summary}"

        nodes.append(Heading(level=4, content=[Text(content=heading_text)]))

        # Description
        description = operation.get("description")
        if description:
            nodes.append(Paragraph(content=[Text(content=description)]))

        # Deprecated notice
        if operation.get("deprecated"):
            nodes.append(Paragraph(content=[Strong(content=[Text(content="DEPRECATED")])]))

        # Parameters
        parameters = operation.get("parameters", [])
        if parameters:
            nodes.append(Paragraph(content=[Strong(content=[Text(content="Parameters:")])]))
            nodes.append(self._build_parameters_table(parameters))

        # Request body (OpenAPI 3.x)
        request_body = operation.get("requestBody")
        if request_body and self.options.include_examples:
            nodes.append(Paragraph(content=[Strong(content=[Text(content="Request Body:")])]))
            nodes.extend(self._build_request_body(request_body))

        # Responses
        responses = operation.get("responses", {})
        if responses:
            nodes.append(Paragraph(content=[Strong(content=[Text(content="Responses:")])]))
            nodes.append(self._build_responses_table(responses))

        return nodes

    def _build_parameters_table(self, parameters: list[dict[str, Any]]) -> Table:
        """Build table for operation parameters.

        Parameters
        ----------
        parameters : list of dict
            Parameter objects

        Returns
        -------
        Table
            Parameters table

        """
        header_row = TableRow(
            cells=[
                TableCell(content=[Text(content="Name")], alignment="left"),
                TableCell(content=[Text(content="Location")], alignment="left"),
                TableCell(content=[Text(content="Type")], alignment="left"),
                TableCell(content=[Text(content="Required")], alignment="center"),
                TableCell(content=[Text(content="Description")], alignment="left"),
            ],
            is_header=True,
        )

        data_rows = []
        for param in parameters:
            name = param.get("name", "")
            location = param.get("in", "")
            required = "Yes" if param.get("required", False) else "No"
            description = param.get("description", "")

            # Get type from schema (OpenAPI 3.x) or directly (Swagger 2.0)
            param_type = ""
            if "schema" in param:
                param_type = self._get_schema_type_string(param["schema"])
            elif "type" in param:
                param_type = param["type"]

            data_rows.append(
                TableRow(
                    cells=[
                        TableCell(content=[Text(content=name)], alignment="left"),
                        TableCell(content=[Text(content=location)], alignment="left"),
                        TableCell(content=[Text(content=param_type)], alignment="left"),
                        TableCell(content=[Text(content=required)], alignment="center"),
                        TableCell(content=[Text(content=description)], alignment="left"),
                    ],
                    is_header=False,
                )
            )

        return Table(header=header_row, rows=data_rows, alignments=["left", "left", "left", "center", "left"])

    def _build_request_body(self, request_body: dict[str, Any]) -> list[Node]:
        """Build request body section.

        Parameters
        ----------
        request_body : dict
            Request body object

        Returns
        -------
        list of Node
            Request body nodes

        """
        nodes: list[Node] = []

        description = request_body.get("description")
        if description:
            nodes.append(Paragraph(content=[Text(content=description)]))

        # Show content types and schemas
        content = request_body.get("content", {})
        for content_type, media_type in content.items():
            nodes.append(Paragraph(content=[Text(content=f"Content-Type: {content_type}")]))

            schema = media_type.get("schema")
            if schema:
                schema_str = self._format_schema_as_json(schema)
                nodes.append(CodeBlock(content=schema_str, language=self.options.code_block_language))

            # Examples
            example = media_type.get("example")
            if example:
                example_str = json.dumps(example, indent=2)
                nodes.append(Paragraph(content=[Text(content="Example:")]))
                nodes.append(CodeBlock(content=example_str, language=self.options.code_block_language))

        return nodes

    def _build_responses_table(self, responses: dict[str, Any]) -> Table:
        """Build table for operation responses.

        Parameters
        ----------
        responses : dict
            Responses object (status code -> response object)

        Returns
        -------
        Table
            Responses table

        """
        header_row = TableRow(
            cells=[
                TableCell(content=[Text(content="Status")], alignment="center"),
                TableCell(content=[Text(content="Description")], alignment="left"),
                TableCell(content=[Text(content="Schema")], alignment="left"),
            ],
            is_header=True,
        )

        data_rows = []
        for status_code, response in sorted(responses.items()):
            if not isinstance(response, dict):
                continue

            description = response.get("description", "")

            # Get schema from content (OpenAPI 3.x) or directly (Swagger 2.0)
            schema_str = ""
            if "content" in response:
                content = response["content"]
                # Get first content type
                for _content_type, media_type in content.items():
                    if "schema" in media_type:
                        schema_str = self._get_schema_type_string(media_type["schema"])
                        break
            elif "schema" in response:
                schema_str = self._get_schema_type_string(response["schema"])

            data_rows.append(
                TableRow(
                    cells=[
                        TableCell(content=[Text(content=str(status_code))], alignment="center"),
                        TableCell(content=[Text(content=description)], alignment="left"),
                        TableCell(content=[Text(content=schema_str)], alignment="left"),
                    ],
                    is_header=False,
                )
            )

        return Table(header=header_row, rows=data_rows, alignments=["center", "left", "left"])

    def _build_schemas_section(self, spec: dict[str, Any]) -> list[Node]:
        """Build schemas/models section.

        Parameters
        ----------
        spec : dict
            OpenAPI specification

        Returns
        -------
        list of Node
            AST nodes for schemas section

        """
        nodes: list[Node] = []

        # Get schemas from components (OpenAPI 3.x) or definitions (Swagger 2.0)
        schemas = spec.get("components", {}).get("schemas", {})
        if not schemas:
            schemas = spec.get("definitions", {})

        if not schemas:
            return nodes

        nodes.append(Heading(level=2, content=[Text(content="Schemas")]))

        for schema_name, schema in sorted(schemas.items()):
            nodes.append(Heading(level=3, content=[Text(content=schema_name)]))

            description = schema.get("description")
            if description:
                nodes.append(Paragraph(content=[Text(content=description)]))

            # Schema properties
            properties = schema.get("properties", {})
            if properties:
                nodes.append(self._build_schema_properties_table(properties, schema.get("required", [])))

        return nodes

    def _build_schema_properties_table(self, properties: dict[str, Any], required: list[str]) -> Table:
        """Build table for schema properties.

        Parameters
        ----------
        properties : dict
            Schema properties
        required : list
            List of required property names

        Returns
        -------
        Table
            Properties table

        """
        header_row = TableRow(
            cells=[
                TableCell(content=[Text(content="Property")], alignment="left"),
                TableCell(content=[Text(content="Type")], alignment="left"),
                TableCell(content=[Text(content="Required")], alignment="center"),
                TableCell(content=[Text(content="Description")], alignment="left"),
            ],
            is_header=True,
        )

        data_rows = []
        for prop_name, prop_schema in properties.items():
            prop_type = self._get_schema_type_string(prop_schema)
            is_required = "Yes" if prop_name in required else "No"
            description = prop_schema.get("description", "")

            data_rows.append(
                TableRow(
                    cells=[
                        TableCell(content=[Text(content=prop_name)], alignment="left"),
                        TableCell(content=[Text(content=prop_type)], alignment="left"),
                        TableCell(content=[Text(content=is_required)], alignment="center"),
                        TableCell(content=[Text(content=description)], alignment="left"),
                    ],
                    is_header=False,
                )
            )

        return Table(header=header_row, rows=data_rows, alignments=["left", "left", "center", "left"])

    def _get_schema_type_string(self, schema: dict[str, Any], depth: int = 0) -> str:
        """Get string representation of schema type.

        Parameters
        ----------
        schema : dict
            Schema object
        depth : int
            Current recursion depth

        Returns
        -------
        str
            Type string

        """
        if depth > self.options.max_schema_depth:
            return "..."

        if "$ref" in schema:
            if self.options.expand_refs:
                return schema["$ref"].split("/")[-1]
            else:
                return schema["$ref"]

        schema_type = schema.get("type", "object")

        if schema_type == "array":
            items = schema.get("items", {})
            item_type = self._get_schema_type_string(items, depth + 1)
            return f"array[{item_type}]"
        elif schema_type == "object":
            return "object"
        else:
            schema_format = schema.get("format")
            if schema_format:
                return f"{schema_type}({schema_format})"
            return schema_type

    def _format_schema_as_json(self, schema: dict[str, Any]) -> str:
        """Format schema as JSON string.

        Parameters
        ----------
        schema : dict
            Schema object

        Returns
        -------
        str
            JSON string

        """
        try:
            return json.dumps(schema, indent=2)
        except Exception:
            return str(schema)

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from OpenAPI specification.

        Parameters
        ----------
        document : dict
            Parsed OpenAPI specification

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        if not isinstance(document, dict):
            return metadata

        info = document.get("info", {})
        metadata.title = info.get("title")
        metadata.subject = info.get("description")

        # Version as custom field
        if "version" in info:
            metadata.custom["version"] = info["version"]

        # OpenAPI/Swagger version
        if "openapi" in document:
            metadata.custom["openapi_version"] = document["openapi"]
        elif "swagger" in document:
            metadata.custom["swagger_version"] = document["swagger"]

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="openapi",
    extensions=[".yaml", ".yml", ".json"],
    mime_types=["application/vnd.oai.openapi", "application/vnd.oai.openapi+json", "application/x-yaml"],
    magic_bytes=[],
    content_detector=_is_openapi_content,
    parser_class=OpenApiParser,
    renderer_class=None,  # No renderer for now
    renders_as_string=False,
    parser_required_packages=[("PyYAML", "yaml", ">=5.1")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="OpenAPI parsing requires 'PyYAML'. Install with: pip install 'all2md[openapi]'",
    parser_options_class=OpenApiParserOptions,
    renderer_options_class=None,
    description="Parse OpenAPI/Swagger specifications (2.0 and 3.x) to Markdown",
    priority=7,
)

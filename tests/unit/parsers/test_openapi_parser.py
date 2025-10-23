#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for OpenAPI parser."""

import pytest

from all2md.ast import (
    Document,
    Heading,
    Paragraph,
    Strong,
    Table,
    Text,
)
from all2md.exceptions import ParsingError
from all2md.options.openapi import OpenApiParserOptions
from all2md.parsers.openapi import OpenApiParser


class TestOpenApiParser:
    """Tests for OpenAPI parser."""

    def test_simple_openapi(self) -> None:
        """Test parsing simple OpenAPI spec."""
        spec = """openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      summary: Test endpoint
      responses:
        '200':
          description: Success
"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have title heading
        assert isinstance(doc.children[0], Heading)
        assert doc.children[0].level == 1
        assert doc.children[0].content[0].content == "Test API"

    def test_swagger_2_spec(self) -> None:
        """Test parsing Swagger 2.0 spec."""
        spec = """swagger: '2.0'
info:
  title: Swagger API
  version: 1.0.0
paths:
  /items:
    get:
      summary: Get items
      responses:
        '200':
          description: Success
"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert isinstance(doc, Document)
        assert doc.children[0].content[0].content == "Swagger API"

    def test_json_format(self) -> None:
        """Test parsing OpenAPI spec in JSON format."""
        spec = """{
  "openapi": "3.0.0",
  "info": {
    "title": "JSON API",
    "version": "1.0.0"
  },
  "paths": {
    "/test": {
      "get": {
        "responses": {
          "200": {
            "description": "OK"
          }
        }
      }
    }
  }
}"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert isinstance(doc, Document)
        assert doc.children[0].content[0].content == "JSON API"

    def test_metadata_extraction(self) -> None:
        """Test extracting metadata from OpenAPI spec."""
        spec = """openapi: 3.0.0
info:
  title: Metadata Test
  description: Testing metadata extraction
  version: 2.0.0
paths: {}
"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert doc.metadata.get("title") == "Metadata Test"
        assert doc.metadata.get("description") == "Testing metadata extraction"
        assert doc.metadata.get("version") == "2.0.0"
        assert doc.metadata.get("openapi_version") == "3.0.0"

    def test_servers_section(self) -> None:
        """Test parsing servers section."""
        spec = """openapi: 3.0.0
info:
  title: Servers Test
  version: 1.0.0
servers:
  - url: https://api.example.com
    description: Production
  - url: https://staging.example.com
    description: Staging
paths: {}
"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        # Find servers heading
        servers_heading = None
        for child in doc.children:
            if isinstance(child, Heading) and child.level == 2:
                if child.content[0].content == "Servers":
                    servers_heading = child
                    break

        assert servers_heading is not None

    def test_tags_grouping(self) -> None:
        """Test grouping paths by tags."""
        spec = """openapi: 3.0.0
info:
  title: Tags Test
  version: 1.0.0
paths:
  /users:
    get:
      tags:
        - users
      summary: Get users
      responses:
        '200':
          description: Success
  /products:
    get:
      tags:
        - products
      summary: Get products
      responses:
        '200':
          description: Success
"""
        parser = OpenApiParser(OpenApiParserOptions(group_by_tag=True))
        doc = parser.parse(spec.encode("utf-8"))

        # Should have tag headings
        tag_headings = [
            child for child in doc.children if isinstance(child, Heading) and child.level == 3
        ]
        assert len(tag_headings) >= 2

    def test_schemas_section(self) -> None:
        """Test parsing schemas section."""
        spec = """openapi: 3.0.0
info:
  title: Schemas Test
  version: 1.0.0
paths: {}
components:
  schemas:
    User:
      type: object
      required:
        - id
      properties:
        id:
          type: integer
          description: User ID
        name:
          type: string
"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        # Find schemas heading
        schemas_heading = None
        for child in doc.children:
            if isinstance(child, Heading) and child.level == 2:
                if child.content[0].content == "Schemas":
                    schemas_heading = child
                    break

        assert schemas_heading is not None

    def test_include_schemas_option(self) -> None:
        """Test include_schemas option."""
        spec = """openapi: 3.0.0
info:
  title: Test
  version: 1.0.0
paths: {}
components:
  schemas:
    Test:
      type: object
"""
        # With schemas
        parser = OpenApiParser(OpenApiParserOptions(include_schemas=True))
        doc = parser.parse(spec.encode("utf-8"))

        schemas_found = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Schemas"
            for child in doc.children
        )
        assert schemas_found

        # Without schemas
        parser = OpenApiParser(OpenApiParserOptions(include_schemas=False))
        doc = parser.parse(spec.encode("utf-8"))

        schemas_found = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Schemas"
            for child in doc.children
        )
        assert not schemas_found

    def test_include_servers_option(self) -> None:
        """Test include_servers option."""
        spec = """openapi: 3.0.0
info:
  title: Test
  version: 1.0.0
servers:
  - url: https://api.example.com
paths: {}
"""
        # With servers
        parser = OpenApiParser(OpenApiParserOptions(include_servers=True))
        doc = parser.parse(spec.encode("utf-8"))

        servers_found = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Servers"
            for child in doc.children
        )
        assert servers_found

        # Without servers
        parser = OpenApiParser(OpenApiParserOptions(include_servers=False))
        doc = parser.parse(spec.encode("utf-8"))

        servers_found = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Servers"
            for child in doc.children
        )
        assert not servers_found

    def test_deprecated_operations(self) -> None:
        """Test handling of deprecated operations."""
        spec = """openapi: 3.0.0
info:
  title: Deprecated Test
  version: 1.0.0
paths:
  /legacy:
    get:
      summary: Legacy endpoint
      deprecated: true
      responses:
        '200':
          description: Success
  /current:
    get:
      summary: Current endpoint
      responses:
        '200':
          description: Success
"""
        # Include deprecated
        parser = OpenApiParser(OpenApiParserOptions(include_deprecated=True))
        doc = parser.parse(spec.encode("utf-8"))

        # Should have DEPRECATED marker
        deprecated_found = any(
            isinstance(child, Paragraph) and
            any(isinstance(node, Strong) and
                any(isinstance(text, Text) and "DEPRECATED" in text.content
                    for text in node.content)
                for node in child.content)
            for child in doc.children
        )
        assert deprecated_found

        # Exclude deprecated
        parser = OpenApiParser(OpenApiParserOptions(include_deprecated=False))
        doc = parser.parse(spec.encode("utf-8"))

        # Should not have legacy endpoint
        has_legacy = any(
            isinstance(child, Heading) and
            any(isinstance(node, Text) and "legacy" in node.content.lower()
                for node in child.content)
            for child in doc.children
        )
        assert not has_legacy

    def test_parameters_table(self) -> None:
        """Test parameters are rendered as table."""
        spec = """openapi: 3.0.0
info:
  title: Params Test
  version: 1.0.0
paths:
  /users/{id}:
    get:
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
        - name: fields
          in: query
          schema:
            type: string
      responses:
        '200':
          description: Success
"""
        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        # Should have table for parameters
        has_table = any(isinstance(child, Table) for child in doc.children)
        assert has_table

    def test_invalid_spec(self) -> None:
        """Test handling of invalid spec."""
        spec = """invalid: yaml
that: is not
an: openapi spec
"""
        parser = OpenApiParser(OpenApiParserOptions(validate_spec=True))

        with pytest.raises(ParsingError):
            parser.parse(spec.encode("utf-8"))

    def test_missing_info_section(self) -> None:
        """Test handling of spec missing info section."""
        spec = """openapi: 3.0.0
paths: {}
"""
        parser = OpenApiParser(OpenApiParserOptions(validate_spec=True))

        with pytest.raises(ParsingError, match="missing required 'info' section"):
            parser.parse(spec.encode("utf-8"))

    def test_max_schema_depth(self) -> None:
        """Test max_schema_depth option."""
        spec = """openapi: 3.0.0
info:
  title: Test
  version: 1.0.0
paths: {}
components:
  schemas:
    DeepNested:
      type: object
      properties:
        level1:
          type: object
          properties:
            level2:
              type: object
              properties:
                level3:
                  type: object
"""
        parser = OpenApiParser(OpenApiParserOptions(max_schema_depth=2))
        doc = parser.parse(spec.encode("utf-8"))

        # Should not recurse beyond max depth
        assert isinstance(doc, Document)


class TestOpenApiDetection:
    """Tests for OpenAPI content detection to prevent false positives."""

    def test_valid_openapi_3x_detected(self) -> None:
        """Test that valid OpenAPI 3.x specs are detected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "3.0.0",
            "paths": {"/test": {}},
            "info": {"title": "Test API", "version": "1.0"}
        }).encode()

        assert _is_openapi_content(spec) is True

    def test_valid_openapi_31_detected(self) -> None:
        """Test that OpenAPI 3.1 specs are detected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "3.1.0",
            "paths": {},
            "info": {"title": "API v3.1"}
        }).encode()

        assert _is_openapi_content(spec) is True

    def test_valid_swagger_20_detected(self) -> None:
        """Test that valid Swagger 2.0 specs are detected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "swagger": "2.0",
            "paths": {},
            "info": {"title": "Swagger API", "version": "1.0"}
        }).encode()

        assert _is_openapi_content(spec) is True

    def test_json_with_wrong_types_not_detected(self) -> None:
        """Test that JSON with correct field names but wrong types is rejected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        # Fields exist but are wrong types
        spec = json.dumps({
            "openapi": "not_a_version",
            "paths": "not_a_dict",
            "info": "not_a_dict"
        }).encode()

        assert _is_openapi_content(spec) is False

    def test_json_missing_title_not_detected(self) -> None:
        """Test that JSON missing required title field in info is rejected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "3.0.0",
            "paths": {},
            "info": {"version": "1.0"}  # Missing required title
        }).encode()

        assert _is_openapi_content(spec) is False

    def test_json_wrong_version_not_detected(self) -> None:
        """Test that JSON with invalid version string is rejected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "4.0.0",  # Invalid version (not 3.x)
            "paths": {},
            "info": {"title": "API", "version": "1.0"}
        }).encode()

        assert _is_openapi_content(spec) is False

    def test_random_json_not_detected(self) -> None:
        """Test that random JSON is not detected as OpenAPI."""
        from all2md.parsers.openapi import _is_openapi_content

        spec = b'{"name": "test", "value": 123}'
        assert _is_openapi_content(spec) is False

    def test_json_with_only_openapi_field_not_detected(self) -> None:
        """Test that JSON with only openapi field is rejected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "3.0.0",
            "data": "some data"
        }).encode()

        assert _is_openapi_content(spec) is False

    def test_yaml_with_numeric_version_detected(self) -> None:
        """Test that YAML with numeric version (e.g., 3.0) is detected."""
        from all2md.parsers.openapi import _is_openapi_content

        spec = b"""openapi: 3.0
info:
  title: Test API
paths: {}
"""
        assert _is_openapi_content(spec) is True

    def test_swagger_yaml_with_quoted_version_detected(self) -> None:
        """Test that Swagger 2.0 with quoted version is detected."""
        from all2md.parsers.openapi import _is_openapi_content

        spec = b"""swagger: '2.0'
info:
  title: Swagger API
  version: 1.0.0
paths: {}
"""
        assert _is_openapi_content(spec) is True

    def test_json_with_paths_not_dict_not_detected(self) -> None:
        """Test that JSON with paths field that is not a dict is rejected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "3.0.0",
            "paths": [],  # Should be dict, not list
            "info": {"title": "API"}
        }).encode()

        assert _is_openapi_content(spec) is False

    def test_json_with_info_not_dict_not_detected(self) -> None:
        """Test that JSON with info field that is not a dict is rejected."""
        from all2md.parsers.openapi import _is_openapi_content
        import json

        spec = json.dumps({
            "openapi": "3.0.0",
            "paths": {},
            "info": []  # Should be dict, not list
        }).encode()

        assert _is_openapi_content(spec) is False

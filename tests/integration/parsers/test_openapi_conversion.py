"""Integration tests for OpenAPI parser.

This module contains integration tests for the OpenAPI converter,
testing full conversion pipelines with various OpenAPI structures and edge cases.
"""

import pytest
from fixtures.generators.openapi_fixtures import (
    create_openapi_complex,
    create_openapi_with_deprecated,
    create_openapi_with_parameters,
    create_openapi_with_request_body,
    create_openapi_with_schemas,
    create_openapi_with_servers,
    create_openapi_with_tags,
    create_simple_openapi,
    create_swagger_2_spec,
)
from utils import assert_markdown_valid

from all2md.ast import (
    Document,
    Heading,
    Table,
)
from all2md.options.openapi import OpenApiParserOptions
from all2md.parsers.openapi import OpenApiParser
from all2md.renderers.markdown import MarkdownRenderer


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationBasic:
    """Test basic OpenAPI integration scenarios."""

    def test_simple_spec_conversion(self) -> None:
        """Test conversion of a simple OpenAPI spec."""
        spec = create_simple_openapi()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have heading
        has_heading = any(isinstance(child, Heading) for child in doc.children)
        assert has_heading

    def test_openapi_to_markdown_conversion(self) -> None:
        """Test converting OpenAPI to Markdown via AST."""
        spec = create_simple_openapi()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert len(result) > 0
        assert_markdown_valid(result)
        assert "Simple API" in result

    def test_swagger_2_conversion(self) -> None:
        """Test converting Swagger 2.0 spec."""
        spec = create_swagger_2_spec()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "Swagger 2.0 API" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationServers:
    """Test OpenAPI server handling."""

    def test_servers_section_rendering(self) -> None:
        """Test rendering of servers section."""
        spec = create_openapi_with_servers()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        # Should have servers heading
        has_servers = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Servers"
            for child in doc.children
        )
        assert has_servers

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "Servers" in result
        assert "api.example.com" in result
        assert "staging.example.com" in result

    def test_servers_disabled(self) -> None:
        """Test disabling servers section."""
        spec = create_openapi_with_servers()

        parser = OpenApiParser(OpenApiParserOptions(include_servers=False))
        doc = parser.parse(spec.encode("utf-8"))

        # Should not have servers heading
        has_servers = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Servers"
            for child in doc.children
        )
        assert not has_servers


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationParameters:
    """Test OpenAPI parameter handling."""

    def test_parameters_rendering(self) -> None:
        """Test rendering of parameters."""
        spec = create_openapi_with_parameters()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        # Should have parameters table
        has_table = any(isinstance(child, Table) for child in doc.children)
        assert has_table

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "userId" in result
        assert "path" in result
        assert "fields" in result
        assert "query" in result


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationRequestBody:
    """Test OpenAPI request body handling."""

    def test_request_body_rendering(self) -> None:
        """Test rendering of request body."""
        spec = create_openapi_with_request_body()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "Request Body" in result
        assert "application/json" in result

    def test_request_body_examples(self) -> None:
        """Test request body examples in code blocks."""
        spec = create_openapi_with_request_body()

        parser = OpenApiParser(OpenApiParserOptions(include_examples=True))
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "John Doe" in result
        assert "john@example.com" in result


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationTags:
    """Test OpenAPI tag grouping."""

    def test_tag_grouping(self) -> None:
        """Test grouping operations by tags."""
        spec = create_openapi_with_tags()

        parser = OpenApiParser(OpenApiParserOptions(group_by_tag=True))
        doc = parser.parse(spec.encode("utf-8"))

        # Should have tag headings
        tag_headings = [child for child in doc.children if isinstance(child, Heading) and child.level == 3]
        assert len(tag_headings) >= 2

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "### users" in result or "users" in result.lower()
        assert "### products" in result or "products" in result.lower()

    def test_no_tag_grouping(self) -> None:
        """Test sequential listing without tag grouping."""
        spec = create_openapi_with_tags()

        parser = OpenApiParser(OpenApiParserOptions(group_by_tag=False))
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Should still have content
        assert "users" in result.lower() or "products" in result.lower()


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationSchemas:
    """Test OpenAPI schema handling."""

    def test_schemas_section_rendering(self) -> None:
        """Test rendering of schemas section."""
        spec = create_openapi_with_schemas()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        # Should have schemas heading
        has_schemas = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Schemas"
            for child in doc.children
        )
        assert has_schemas

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "Schemas" in result
        assert "User" in result

    def test_schemas_disabled(self) -> None:
        """Test disabling schemas section."""
        spec = create_openapi_with_schemas()

        parser = OpenApiParser(OpenApiParserOptions(include_schemas=False))
        doc = parser.parse(spec.encode("utf-8"))

        # Should not have schemas heading
        has_schemas = any(
            isinstance(child, Heading) and child.level == 2 and child.content[0].content == "Schemas"
            for child in doc.children
        )
        assert not has_schemas


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationDeprecated:
    """Test OpenAPI deprecated operations handling."""

    def test_deprecated_included(self) -> None:
        """Test including deprecated operations."""
        spec = create_openapi_with_deprecated()

        parser = OpenApiParser(OpenApiParserOptions(include_deprecated=True))
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "legacy" in result.lower()
        assert "DEPRECATED" in result

    def test_deprecated_excluded(self) -> None:
        """Test excluding deprecated operations."""
        spec = create_openapi_with_deprecated()

        parser = OpenApiParser(OpenApiParserOptions(include_deprecated=False))
        doc = parser.parse(spec.encode("utf-8"))

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Should not have legacy endpoint
        assert "legacy" not in result.lower() or "current" in result.lower()


@pytest.mark.integration
@pytest.mark.openapi
class TestOpenApiIntegrationComplex:
    """Test complex OpenAPI spec conversion."""

    def test_complex_spec_conversion(self) -> None:
        """Test converting a complex OpenAPI spec with all features."""
        spec = create_openapi_complex()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert isinstance(doc, Document)
        assert len(doc.children) > 10  # Should have many sections

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert_markdown_valid(result)
        assert "E-Commerce API" in result
        assert "products" in result.lower()
        assert "orders" in result.lower()
        assert "Servers" in result
        assert "Schemas" in result

    def test_complex_spec_metadata(self) -> None:
        """Test metadata extraction from complex spec."""
        spec = create_openapi_complex()

        parser = OpenApiParser()
        doc = parser.parse(spec.encode("utf-8"))

        assert doc.metadata.get("title") == "E-Commerce API"
        assert "comprehensive" in doc.metadata.get("description", "").lower()
        assert doc.metadata.get("version") == "2.0.0"

"""Golden tests for OpenAPI conversion."""

from __future__ import annotations

import pytest
from fixtures.generators.openapi_fixtures import (
    create_openapi_complex,
    create_openapi_with_parameters,
    create_openapi_with_schemas,
    create_openapi_with_servers,
    create_openapi_with_tags,
    create_simple_openapi,
    create_swagger_2_spec,
    openapi_bytes_io,
)

from all2md import to_markdown


@pytest.mark.golden
@pytest.mark.openapi
@pytest.mark.unit
class TestOpenApiGolden:
    """Golden tests for OpenAPI conversion."""

    def test_simple_openapi(self, snapshot):
        """Test simple OpenAPI spec conversion."""
        spec_bytes = openapi_bytes_io(create_simple_openapi())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

    def test_openapi_with_servers(self, snapshot):
        """Test OpenAPI spec with servers section."""
        spec_bytes = openapi_bytes_io(create_openapi_with_servers())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

    def test_openapi_with_parameters(self, snapshot):
        """Test OpenAPI spec with parameters."""
        spec_bytes = openapi_bytes_io(create_openapi_with_parameters())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

    def test_openapi_with_tags(self, snapshot):
        """Test OpenAPI spec with tags."""
        spec_bytes = openapi_bytes_io(create_openapi_with_tags())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

    def test_openapi_with_schemas(self, snapshot):
        """Test OpenAPI spec with component schemas."""
        spec_bytes = openapi_bytes_io(create_openapi_with_schemas())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

    def test_swagger_2_spec(self, snapshot):
        """Test Swagger 2.0 spec conversion."""
        spec_bytes = openapi_bytes_io(create_swagger_2_spec())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

    def test_complex_openapi(self, snapshot):
        """Test complex OpenAPI spec with all features."""
        spec_bytes = openapi_bytes_io(create_openapi_complex())
        result = to_markdown(spec_bytes, source_format="openapi")
        assert result == snapshot

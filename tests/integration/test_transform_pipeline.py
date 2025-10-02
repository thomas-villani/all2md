#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for transform pipeline."""

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Text
from all2md.ast.transforms import NodeTransformer
from all2md.options import MarkdownOptions
from all2md.transforms import (
    HookContext,
    Pipeline,
    TransformMetadata,
    TransformRegistry,
    render,
)


# Test transforms

class RemoveImagesTransform(NodeTransformer):
    """Transform that removes all images."""

    def visit_image(self, node):
        return None  # Remove


class UppercaseTextTransform(NodeTransformer):
    """Transform that uppercases all text."""

    def visit_text(self, node):
        return Text(
            content=node.content.upper(),
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )


class HeadingOffsetTransform(NodeTransformer):
    """Transform that offsets heading levels."""

    def __init__(self, offset: int = 1):
        self.offset = offset

    def visit_heading(self, node):
        new_level = max(1, min(6, node.level + self.offset))
        return Heading(
            level=new_level,
            content=self._transform_children(node.content),
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )


# Fixtures

@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[
                Text(content="Hello "),
                Link(url="https://example.com", content=[Text(content="world")])
            ]),
            Paragraph(content=[
                Image(url="image.png", alt_text="An image")
            ])
        ],
        metadata={"author": "Test"}
    )


@pytest.fixture
def registry():
    """Create a registry for testing."""
    reg = TransformRegistry()
    reg.clear()
    return reg


# Basic rendering tests

class TestBasicRendering:
    """Tests for basic rendering without transforms."""

    def test_render_simple_document(self, sample_document):
        """Test rendering without any transforms."""
        markdown = render(sample_document)

        assert "# Title" in markdown
        assert "Hello" in markdown
        assert "world" in markdown
        assert "image.png" in markdown

    def test_render_empty_document(self):
        """Test rendering an empty document."""
        doc = Document(children=[])
        markdown = render(doc)

        assert markdown == ""

    def test_render_with_options(self, sample_document):
        """Test rendering with custom options."""
        options = MarkdownOptions(flavor="commonmark", emphasis_symbol="_")
        markdown = render(sample_document, options=options)

        assert "# Title" in markdown

    def test_render_with_kwargs(self, sample_document):
        """Test rendering with options as kwargs."""
        markdown = render(sample_document, flavor="gfm", emphasis_symbol="*")

        assert "# Title" in markdown


# Transform tests

class TestTransformExecution:
    """Tests for transform execution."""

    def test_single_transform_instance(self, sample_document):
        """Test applying a single transform instance."""
        transform = RemoveImagesTransform()
        markdown = render(sample_document, transforms=[transform])

        assert "# Title" in markdown
        assert "Hello" in markdown
        assert "image.png" not in markdown  # Image removed

    def test_multiple_transform_instances(self, sample_document):
        """Test applying multiple transform instances."""
        transforms = [
            RemoveImagesTransform(),
            UppercaseTextTransform()
        ]
        markdown = render(sample_document, transforms=transforms)

        assert "TITLE" in markdown
        assert "HELLO" in markdown
        assert "image.png" not in markdown

    def test_transform_with_parameters(self, sample_document):
        """Test transform with parameters."""
        transform = HeadingOffsetTransform(offset=2)
        markdown = render(sample_document, transforms=[transform])

        # H1 becomes H3
        assert "### Title" in markdown

    def test_transform_by_name(self, sample_document, registry):
        """Test applying transform by name."""
        # Register transform
        metadata = TransformMetadata(
            name="remove-images",
            description="Remove images",
            transformer_class=RemoveImagesTransform
        )
        registry.register(metadata)

        markdown = render(sample_document, transforms=["remove-images"])

        assert "image.png" not in markdown

    def test_mixed_transforms(self, sample_document, registry):
        """Test mixing named and instance transforms."""
        metadata = TransformMetadata(
            name="remove-images",
            description="Remove images",
            transformer_class=RemoveImagesTransform
        )
        registry.register(metadata)

        transforms = [
            "remove-images",
            UppercaseTextTransform()
        ]
        markdown = render(sample_document, transforms=transforms)

        assert "TITLE" in markdown
        assert "image.png" not in markdown


# Hook tests

class TestHookExecution:
    """Tests for hook execution."""

    def test_pipeline_hook_pre_render(self, sample_document):
        """Test pre_render hook."""
        called = []

        def pre_render_hook(doc, context):
            called.append('pre_render')
            return doc

        markdown = render(
            sample_document,
            hooks={'pre_render': [pre_render_hook]}
        )

        assert called == ['pre_render']
        assert "# Title" in markdown

    def test_pipeline_hook_post_render(self, sample_document):
        """Test post_render hook."""
        def post_render_hook(md, context):
            return md + "\n\n---\nFooter"

        markdown = render(
            sample_document,
            hooks={'post_render': [post_render_hook]}
        )

        assert "Footer" in markdown

    def test_element_hook_image(self, sample_document):
        """Test element hook for images."""
        def log_image(node, context):
            context.set_shared('image_url', node.url)
            return node

        hooks = {'image': [log_image]}
        markdown = render(sample_document, hooks=hooks)

        # Hook was called (we can't access context here, but no error means success)
        assert "image.png" in markdown

    def test_element_hook_removes_node(self, sample_document):
        """Test element hook that removes nodes."""
        def remove_images(node, context):
            return None  # Remove all images

        markdown = render(
            sample_document,
            hooks={'image': [remove_images]}
        )

        assert "image.png" not in markdown

    def test_element_hook_modifies_node(self, sample_document):
        """Test element hook that modifies nodes."""
        def uppercase_text(node, context):
            return Text(
                content=node.content.upper(),
                metadata=node.metadata,
                source_location=node.source_location
            )

        markdown = render(
            sample_document,
            hooks={'text': [uppercase_text]}
        )

        assert "TITLE" in markdown
        assert "HELLO" in markdown

    def test_hook_chain(self, sample_document):
        """Test multiple hooks for same target execute in order."""
        results = []

        def hook1(doc, context):
            results.append(1)
            return doc

        def hook2(doc, context):
            results.append(2)
            return doc

        markdown = render(
            sample_document,
            hooks={'pre_render': [hook1, hook2]}
        )

        assert results == [1, 2]


# Context tests

class TestContextPassing:
    """Tests for context passing through pipeline."""

    def test_shared_context_between_hooks(self, sample_document):
        """Test hooks can share data via context."""
        def count_images(node, context):
            count = context.get_shared('image_count', 0)
            context.set_shared('image_count', count + 1)
            return node

        def add_image_count(md, context):
            count = context.get_shared('image_count', 0)
            return f"{md}\n\nImages: {count}"

        markdown = render(
            sample_document,
            hooks={
                'image': [count_images],
                'post_render': [add_image_count]
            }
        )

        assert "Images: 1" in markdown

    def test_context_has_metadata(self, sample_document):
        """Test context contains document metadata."""
        def check_metadata(doc, context):
            assert 'author' in context.metadata
            assert context.metadata['author'] == "Test"
            return doc

        markdown = render(
            sample_document,
            hooks={'pre_render': [check_metadata]}
        )

    def test_context_has_document(self, sample_document):
        """Test context contains document reference."""
        def check_document(doc, context):
            assert context.document is not None
            assert isinstance(context.document, Document)
            return doc

        markdown = render(
            sample_document,
            hooks={'pre_render': [check_document]}
        )


# Combined tests

class TestCombinedTransformsAndHooks:
    """Tests for combining transforms and hooks."""

    def test_transform_then_hooks(self, sample_document):
        """Test transforms execute before element hooks."""
        # Transform uppercases text, then hook verifies it's uppercase
        def verify_uppercase(node, context):
            assert node.content.isupper()
            return node

        markdown = render(
            sample_document,
            transforms=[UppercaseTextTransform()],
            hooks={'text': [verify_uppercase]}
        )

        assert "TITLE" in markdown

    def test_complex_pipeline(self, sample_document):
        """Test complex pipeline with multiple transforms and hooks."""
        results = []

        def track_pre_render(doc, context):
            results.append('pre_render')
            return doc

        def track_post_render(md, context):
            results.append('post_render')
            return md

        def track_image(node, context):
            results.append('image')
            return node

        markdown = render(
            sample_document,
            transforms=[HeadingOffsetTransform(offset=1)],
            hooks={
                'pre_render': [track_pre_render],
                'image': [track_image],
                'post_render': [track_post_render]
            }
        )

        assert results == ['pre_render', 'image', 'post_render']
        assert "## Title" in markdown  # H1 → H2


# Error handling tests

class TestErrorHandling:
    """Tests for error handling in pipeline."""

    def test_invalid_transform_type(self, sample_document):
        """Test error with invalid transform type."""
        with pytest.raises(TypeError, match="must be str or NodeTransformer"):
            render(sample_document, transforms=[123])  # type: ignore

    def test_transform_not_found(self, sample_document):
        """Test error when transform name not found."""
        with pytest.raises(ValueError, match="not found"):
            render(sample_document, transforms=["nonexistent"])

    def test_hook_error_logged(self, sample_document, caplog):
        """Test hook errors are logged but don't crash pipeline."""
        def failing_hook(node, context):
            raise RuntimeError("Hook failed!")

        # Should not raise, just log
        markdown = render(
            sample_document,
            hooks={'image': [failing_hook]}
        )

        assert "Hook failed" in caplog.text
        # Pipeline should complete
        assert "# Title" in markdown


# Pipeline class tests

class TestPipelineClass:
    """Tests for Pipeline class directly."""

    def test_pipeline_initialization(self):
        """Test Pipeline initialization."""
        pipeline = Pipeline(
            transforms=[UppercaseTextTransform()],
            hooks={'pre_render': [lambda doc, ctx: doc]},
            options=MarkdownOptions(flavor="gfm")
        )

        assert pipeline.transforms is not None
        assert pipeline.hook_manager is not None
        assert pipeline.options.flavor == "gfm"

    def test_pipeline_execute(self, sample_document):
        """Test Pipeline.execute()."""
        pipeline = Pipeline(transforms=[RemoveImagesTransform()])
        markdown = pipeline.execute(sample_document)

        assert "# Title" in markdown
        assert "image.png" not in markdown

    def test_empty_pipeline(self, sample_document):
        """Test pipeline with no transforms or hooks."""
        pipeline = Pipeline()
        markdown = pipeline.execute(sample_document)

        assert "# Title" in markdown
        assert "image.png" in markdown


# Dependency resolution tests

class TestDependencyResolution:
    """Tests for transform dependency resolution."""

    def test_dependencies_resolved_automatically(self, sample_document, registry):
        """Test dependencies are resolved automatically."""
        # Create dependent transforms
        class TransformA(NodeTransformer):
            pass

        class TransformB(NodeTransformer):
            pass

        metadata_a = TransformMetadata(
            name="transform-a",
            description="Transform A",
            transformer_class=TransformA,
            priority=100
        )

        metadata_b = TransformMetadata(
            name="transform-b",
            description="Transform B",
            transformer_class=TransformB,
            dependencies=["transform-a"],
            priority=200
        )

        registry.register(metadata_a)
        registry.register(metadata_b)

        # Request only B - should automatically include A
        markdown = render(sample_document, transforms=["transform-b"])

        # Should not crash (A dependency satisfied)
        assert "# Title" in markdown

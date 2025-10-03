#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for transform pipeline."""

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Text
from all2md.ast.transforms import NodeTransformer
from all2md.options import MarkdownOptions
from all2md.transforms import (
    Pipeline,
    TransformMetadata,
    TransformRegistry,
    apply,
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


# Apply function tests (AST-only processing without rendering)

class TestApplyFunction:
    """Tests for apply() function - AST transformation without rendering."""

    def test_apply_returns_document(self, sample_document):
        """Test that apply() returns a Document, not a string."""
        result = apply(sample_document)

        assert isinstance(result, Document)
        assert not isinstance(result, str)

    def test_apply_with_no_transforms_or_hooks(self, sample_document):
        """Test apply() with no transforms or hooks returns unchanged document."""
        result = apply(sample_document)

        # Document structure should be unchanged
        assert len(result.children) == 3
        assert isinstance(result.children[0], Heading)
        assert isinstance(result.children[1], Paragraph)
        assert isinstance(result.children[2], Paragraph)

    def test_apply_with_single_transform(self, sample_document):
        """Test apply() with single transform modifies AST."""
        result = apply(sample_document, transforms=[RemoveImagesTransform()])

        # Check document structure
        assert isinstance(result, Document)
        assert len(result.children) == 3

        # Image should be removed from paragraph
        last_para = result.children[2]
        assert isinstance(last_para, Paragraph)
        assert len(last_para.content) == 0  # Image was removed

    def test_apply_with_multiple_transforms(self, sample_document):
        """Test apply() with multiple transforms."""
        transforms = [
            RemoveImagesTransform(),
            UppercaseTextTransform()
        ]
        result = apply(sample_document, transforms=transforms)

        # Check document structure
        assert isinstance(result, Document)

        # Text should be uppercased
        heading = result.children[0]
        assert isinstance(heading, Heading)
        assert heading.content[0].content == "TITLE"

        # Image should be removed
        last_para = result.children[2]
        assert len(last_para.content) == 0

    def test_apply_with_transform_instance_with_params(self, sample_document):
        """Test apply() with parameterized transform."""
        result = apply(sample_document, transforms=[HeadingOffsetTransform(offset=2)])

        # Heading level should change from 1 to 3
        heading = result.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 3

    def test_apply_with_element_hook(self, sample_document):
        """Test apply() with element hook modifies AST."""
        hook_called = []

        def modify_image(node, context):
            hook_called.append(node.url)
            # Modify the image URL
            return Image(
                url="modified.png",
                alt_text=node.alt_text,
                metadata=node.metadata.copy(),
                source_location=node.source_location
            )

        result = apply(sample_document, hooks={'image': [modify_image]})

        # Hook should have been called
        assert hook_called == ["image.png"]

        # Image URL should be modified in AST
        last_para = result.children[2]
        image_node = last_para.content[0]
        assert isinstance(image_node, Image)
        assert image_node.url == "modified.png"

    def test_apply_with_pipeline_hook(self, sample_document):
        """Test apply() with pipeline hook."""
        hook_calls = []

        def pre_render_hook(doc, context):
            hook_calls.append('pre_render')
            return doc

        def post_ast_hook(doc, context):
            hook_calls.append('post_ast')
            return doc

        result = apply(
            sample_document,
            hooks={
                'post_ast': [post_ast_hook],
                'pre_render': [pre_render_hook]
            }
        )

        # Both hooks should be called
        assert 'post_ast' in hook_calls
        assert 'pre_render' in hook_calls
        assert isinstance(result, Document)

    def test_apply_does_not_execute_post_render_hook(self, sample_document):
        """Test that apply() does not execute post_render hooks."""
        hook_calls = []

        def post_render_hook(output, context):
            hook_calls.append('post_render')
            return output

        result = apply(
            sample_document,
            hooks={'post_render': [post_render_hook]}
        )

        # post_render should NOT be called since no rendering happens
        assert 'post_render' not in hook_calls
        assert isinstance(result, Document)

    def test_apply_with_transforms_and_hooks(self, sample_document):
        """Test apply() with both transforms and hooks."""
        hook_calls = []

        def link_hook(node, context):
            hook_calls.append(node.url)
            # Modify link URL
            return Link(
                url="https://modified.com",
                content=node.content,
                title=node.title,
                metadata=node.metadata.copy(),
                source_location=node.source_location
            )

        result = apply(
            sample_document,
            transforms=[RemoveImagesTransform()],
            hooks={'link': [link_hook]}
        )

        # Image should be removed
        last_para = result.children[2]
        assert len(last_para.content) == 0

        # Link should be modified
        assert hook_calls == ["https://example.com"]
        second_para = result.children[1]
        link_node = second_para.content[1]
        assert isinstance(link_node, Link)
        assert link_node.url == "https://modified.com"

    def test_apply_chaining(self, sample_document):
        """Test chaining multiple apply() calls."""
        # First pass: remove images
        doc1 = apply(sample_document, transforms=[RemoveImagesTransform()])

        # Second pass: uppercase text
        doc2 = apply(doc1, transforms=[UppercaseTextTransform()])

        # Check both transformations applied
        assert isinstance(doc2, Document)

        # Image removed
        last_para = doc2.children[2]
        assert len(last_para.content) == 0

        # Text uppercased
        heading = doc2.children[0]
        assert heading.content[0].content == "TITLE"

    def test_apply_then_render(self, sample_document):
        """Test using apply() for AST processing then render() for output."""
        # Process AST
        processed = apply(
            sample_document,
            transforms=[RemoveImagesTransform(), UppercaseTextTransform()]
        )

        # Then render
        markdown = render(processed)

        # Check final output
        assert isinstance(markdown, str)
        assert "TITLE" in markdown
        assert "HELLO" in markdown
        assert "image.png" not in markdown

    def test_apply_preserves_metadata(self, sample_document):
        """Test that apply() preserves document metadata."""
        result = apply(sample_document, transforms=[RemoveImagesTransform()])

        assert result.metadata == {"author": "Test"}

    def test_apply_with_transform_by_name(self, sample_document, registry):
        """Test apply() with named transform from registry."""
        metadata = TransformMetadata(
            name="remove-images",
            description="Remove images",
            transformer_class=RemoveImagesTransform
        )
        registry.register(metadata)

        result = apply(sample_document, transforms=["remove-images"])

        # Image should be removed
        last_para = result.children[2]
        assert len(last_para.content) == 0

    def test_apply_hook_removes_document_raises(self, sample_document):
        """Test that apply() raises ValueError if hook removes document."""
        def bad_hook(doc, context):
            return None  # Remove document

        with pytest.raises(ValueError, match="removed document"):
            apply(sample_document, hooks={'pre_render': [bad_hook]})

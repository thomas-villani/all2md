#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for hook system."""

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Text
from all2md.transforms import HookContext, HookManager


@pytest.fixture
def manager():
    """Create a fresh hook manager for each test."""
    mgr = HookManager()
    mgr.clear()
    return mgr


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
        ]
    )


@pytest.fixture
def context(sample_document):
    """Create a sample hook context."""
    return HookContext(
        document=sample_document,
        metadata={"author": "Test Author"},
        shared={}
    )


class TestHookContext:
    """Tests for HookContext class."""

    def test_basic_context(self, sample_document):
        """Test basic context creation."""
        context = HookContext(document=sample_document)

        assert context.document == sample_document
        assert context.metadata == {}
        assert context.shared == {}
        assert context.transform_name is None
        assert context.node_path == []

    def test_context_with_metadata(self, sample_document):
        """Test context with metadata."""
        metadata = {"author": "Test", "version": "1.0"}
        context = HookContext(document=sample_document, metadata=metadata)

        assert context.metadata == metadata

    def test_context_with_shared_state(self, sample_document):
        """Test context with shared state."""
        shared = {"counter": 0, "results": []}
        context = HookContext(document=sample_document, shared=shared)

        assert context.shared == shared

    def test_get_shared(self, context):
        """Test getting shared state values."""
        context.shared["key1"] = "value1"

        assert context.get_shared("key1") == "value1"
        assert context.get_shared("missing") is None
        assert context.get_shared("missing", "default") == "default"

    def test_set_shared(self, context):
        """Test setting shared state values."""
        context.set_shared("key1", "value1")

        assert context.shared["key1"] == "value1"

    def test_shared_state_mutable(self, sample_document):
        """Test shared state is mutable across hooks."""
        shared = {"counter": 0}
        context = HookContext(document=sample_document, shared=shared)

        # Modify shared state
        context.set_shared("counter", context.get_shared("counter", 0) + 1)

        # Original dict should be modified
        assert shared["counter"] == 1


class TestHookManager:
    """Tests for HookManager class."""

    def test_register_hook(self, manager):
        """Test registering a hook."""
        def my_hook(node, context):
            return node

        manager.register_hook('image', my_hook)

        assert manager.has_hooks('image')

    def test_register_hook_with_priority(self, manager):
        """Test registering hooks with different priorities."""
        results = []

        def hook1(node, context):
            results.append(1)
            return node

        def hook2(node, context):
            results.append(2)
            return node

        # Register in reverse priority order
        manager.register_hook('image', hook2, priority=200)
        manager.register_hook('image', hook1, priority=100)

        # Execute
        image = Image(url="test.png")
        context = HookContext(document=Document())
        manager.execute_hooks('image', image, context)

        # Lower priority runs first
        assert results == [1, 2]

    def test_unregister_hook(self, manager):
        """Test unregistering a hook."""
        def my_hook(node, context):
            return node

        manager.register_hook('image', my_hook)
        assert manager.has_hooks('image')

        result = manager.unregister_hook('image', my_hook)
        assert result is True
        assert not manager.has_hooks('image')

    def test_unregister_nonexistent_hook(self, manager):
        """Test unregistering non-existent hook returns False."""
        def my_hook(node, context):
            return node

        result = manager.unregister_hook('image', my_hook)
        assert result is False

    def test_execute_hooks_no_hooks(self, manager, context):
        """Test executing hooks when none are registered."""
        image = Image(url="test.png")

        result = manager.execute_hooks('image', image, context)
        assert result == image  # Returns unchanged

    def test_execute_hooks_single(self, manager, context):
        """Test executing a single hook."""
        def uppercase_url(node, context):
            node.url = node.url.upper()
            return node

        manager.register_hook('image', uppercase_url)

        image = Image(url="test.png")
        result = manager.execute_hooks('image', image, context)

        assert result.url == "TEST.PNG"

    def test_execute_hooks_chain(self, manager, context):
        """Test executing multiple hooks in chain."""
        def add_prefix(node, context):
            node.url = "http://" + node.url
            return node

        def uppercase(node, context):
            node.url = node.url.upper()
            return node

        manager.register_hook('image', add_prefix, priority=100)
        manager.register_hook('image', uppercase, priority=200)

        image = Image(url="example.com")
        result = manager.execute_hooks('image', image, context)

        assert result.url == "HTTP://EXAMPLE.COM"

    def test_execute_hooks_remove_node(self, manager, context):
        """Test hook can remove node by returning None."""
        def remove_all(node, context):
            return None

        manager.register_hook('image', remove_all)

        image = Image(url="test.png")
        result = manager.execute_hooks('image', image, context)

        assert result is None

    def test_execute_hooks_with_context(self, manager, context):
        """Test hooks receive and can modify context."""
        def count_images(node, context):
            count = context.get_shared("image_count", 0)
            context.set_shared("image_count", count + 1)
            return node

        manager.register_hook('image', count_images)

        # Execute multiple times
        for i in range(3):
            image = Image(url=f"image{i}.png")
            manager.execute_hooks('image', image, context)

        assert context.get_shared("image_count") == 3

    def test_execute_hooks_error_handling(self, manager, context, caplog):
        """Test hook errors are logged but don't break pipeline."""
        def failing_hook(node, context):
            raise RuntimeError("Hook failed!")

        def safe_hook(node, context):
            node.url = "modified.png"
            return node

        manager.register_hook('image', failing_hook, priority=100)
        manager.register_hook('image', safe_hook, priority=200)

        image = Image(url="test.png")
        result = manager.execute_hooks('image', image, context)

        # Hook should log error but continue
        assert "Hook failed" in caplog.text
        # Safe hook should still run
        assert result.url == "modified.png"

    def test_has_hooks(self, manager):
        """Test checking for registered hooks."""
        def my_hook(node, context):
            return node

        assert not manager.has_hooks('image')

        manager.register_hook('image', my_hook)
        assert manager.has_hooks('image')

    def test_get_node_type_document(self, manager):
        """Test getting node type for Document."""
        doc = Document()
        assert manager.get_node_type(doc) == 'document'

    def test_get_node_type_heading(self, manager):
        """Test getting node type for Heading."""
        heading = Heading(level=1, content=[])
        assert manager.get_node_type(heading) == 'heading'

    def test_get_node_type_paragraph(self, manager):
        """Test getting node type for Paragraph."""
        para = Paragraph(content=[])
        assert manager.get_node_type(para) == 'paragraph'

    def test_get_node_type_text(self, manager):
        """Test getting node type for Text."""
        text = Text(content="Hello")
        assert manager.get_node_type(text) == 'text'

    def test_get_node_type_image(self, manager):
        """Test getting node type for Image."""
        image = Image(url="test.png")
        assert manager.get_node_type(image) == 'image'

    def test_get_node_type_link(self, manager):
        """Test getting node type for Link."""
        link = Link(url="https://example.com", content=[])
        assert manager.get_node_type(link) == 'link'

    def test_clear_hooks(self, manager):
        """Test clearing all hooks."""
        def my_hook(node, context):
            return node

        manager.register_hook('image', my_hook)
        manager.register_hook('link', my_hook)

        assert manager.has_hooks('image')
        assert manager.has_hooks('link')

        manager.clear()

        assert not manager.has_hooks('image')
        assert not manager.has_hooks('link')

    def test_pipeline_hooks(self, manager, context):
        """Test pipeline stage hooks."""
        results = []

        def pre_render_hook(doc, context):
            results.append('pre_render')
            return doc

        def post_render_hook(markdown, context):
            results.append('post_render')
            return markdown

        manager.register_hook('pre_render', pre_render_hook)
        manager.register_hook('post_render', post_render_hook)

        doc = Document()
        manager.execute_hooks('pre_render', doc, context)
        manager.execute_hooks('post_render', "# Markdown", context)

        assert results == ['pre_render', 'post_render']

    def test_multiple_hooks_same_priority(self, manager, context):
        """Test multiple hooks with same priority execute in registration order."""
        results = []

        def hook1(node, context):
            results.append(1)
            return node

        def hook2(node, context):
            results.append(2)
            return node

        def hook3(node, context):
            results.append(3)
            return node

        # All have same priority
        manager.register_hook('image', hook1, priority=100)
        manager.register_hook('image', hook2, priority=100)
        manager.register_hook('image', hook3, priority=100)

        image = Image(url="test.png")
        manager.execute_hooks('image', image, context)

        assert results == [1, 2, 3]  # Registration order

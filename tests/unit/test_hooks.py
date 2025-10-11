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

    def test_strict_mode_disabled_by_default(self):
        """Test strict mode is disabled by default."""
        manager = HookManager()
        assert manager.strict is False

    def test_strict_mode_can_be_enabled(self):
        """Test strict mode can be enabled."""
        manager = HookManager(strict=True)
        assert manager.strict is True

    def test_strict_mode_reraises_exceptions(self, context):
        """Test strict mode re-raises exceptions from hooks."""
        manager = HookManager(strict=True)

        def failing_hook(node, context):
            raise RuntimeError("Hook failed in strict mode!")

        manager.register_hook('image', failing_hook)

        image = Image(url="test.png")

        # In strict mode, exception should be re-raised
        with pytest.raises(RuntimeError, match="Hook failed in strict mode!"):
            manager.execute_hooks('image', image, context)

    def test_non_strict_mode_continues_on_error(self, context, caplog):
        """Test non-strict mode logs errors and continues."""
        manager = HookManager(strict=False)

        def failing_hook(node, context):
            raise RuntimeError("Hook failed!")

        def safe_hook(node, context):
            node.url = "modified.png"
            return node

        manager.register_hook('image', failing_hook, priority=100)
        manager.register_hook('image', safe_hook, priority=200)

        image = Image(url="test.png")
        result = manager.execute_hooks('image', image, context)

        # In non-strict mode, error is logged but execution continues
        assert "Hook failed" in caplog.text
        # Safe hook should still execute
        assert result.url == "modified.png"

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


class TestHookAwareVisitor:
    """Tests for HookAwareVisitor class."""

    def test_node_path_integrity_when_hook_replaces_node(self):
        """Test that node_path is correctly maintained when hooks return different nodes.

        This test verifies the fix for the node path handling bug where if a hook
        returns a different node object, the path stack should still be cleaned up
        correctly.
        """
        from all2md.transforms.pipeline import HookAwareVisitor

        # Create test document
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Original text")
            ])
        ])

        # Create hook manager and context
        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        # Track path state during hook execution
        path_states = []

        def replace_text_hook(node, ctx):
            # Record path state when hook is called
            path_states.append(len(ctx.node_path))

            # Return a DIFFERENT Text node (not the same object)
            return Text(content="Replaced text")

        # Register hook that replaces nodes
        manager.register_hook('text', replace_text_hook)

        # Create visitor and transform the document
        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Verify the hook was called (path length should be > 0 during execution)
        assert len(path_states) > 0
        assert path_states[0] > 0  # Path should contain nodes during hook

        # Most importantly: verify the path is clean after transformation
        # This is the bug fix - previously the path would retain the original node
        assert len(context.node_path) == 0, "Node path should be empty after transformation completes"

    def test_node_path_integrity_with_nested_replacements(self):
        """Test node_path with multiple nested hooks that replace nodes."""
        from all2md.transforms.pipeline import HookAwareVisitor

        # Create nested document structure
        doc = Document(children=[
            Paragraph(content=[
                Link(url="http://example.com", content=[
                    Text(content="link text")
                ])
            ])
        ])

        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        # Track all path states
        recorded_paths = []

        def record_and_replace_link(node, ctx):
            # Record current path
            recorded_paths.append(('link', list(ctx.node_path)))
            # Return new Link object
            return Link(url="http://replaced.com", content=node.content)

        def record_and_replace_text(node, ctx):
            # Record current path
            recorded_paths.append(('text', list(ctx.node_path)))
            # Return new Text object
            return Text(content="replaced text")

        manager.register_hook('link', record_and_replace_link)
        manager.register_hook('text', record_and_replace_text)

        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Path should be clean after all transformations
        assert len(context.node_path) == 0, "Node path should be clean after nested transformations"

        # Verify hooks were called
        assert len(recorded_paths) > 0

    def test_node_path_cleaned_when_hook_removes_node(self):
        """Test that node_path is cleaned up when hook returns None."""
        from all2md.transforms.pipeline import HookAwareVisitor

        doc = Document(children=[
            Paragraph(content=[
                Image(url="test.png", alt_text="test")
            ])
        ])

        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        def remove_image_hook(node, ctx):
            # Return None to remove the node
            return None

        manager.register_hook('image', remove_image_hook)

        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Path should still be clean after node removal
        assert len(context.node_path) == 0, "Node path should be clean even when nodes are removed"

    def test_descendants_can_see_ancestors_in_node_path(self):
        """Test that descendant hooks can see full ancestry in node_path.

        This test verifies the fix for the node_path maintenance issue where
        descendants couldn't see their ancestors because parents were popped
        before child traversal.

        Use case: "act only on images inside blockquotes"
        """
        from all2md.ast import BlockQuote
        from all2md.transforms.pipeline import HookAwareVisitor

        # Create nested structure: Document > BlockQuote > Paragraph > Image
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[
                    Image(url="nested.png", alt_text="nested image")
                ])
            ])
        ])

        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        # Track path when image hook executes
        captured_path = []

        def image_hook(node, ctx):
            # Capture the full node_path when this hook executes
            # The path should contain all ancestors: Document, BlockQuote, Paragraph, Image
            captured_path.extend(ctx.node_path)
            return node

        # Register hook ONLY on image (not on blockquote or paragraph)
        manager.register_hook('image', image_hook)

        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Verify the image hook was called and captured the path
        assert len(captured_path) > 0, "Image hook should have been called"

        # Verify full ancestry is in the path
        # Path should contain: [Document, BlockQuote, Paragraph, Image]
        assert len(captured_path) == 4, f"Expected 4 nodes in path, got {len(captured_path)}"

        # Verify the types are correct in order
        assert isinstance(captured_path[0], Document), "First ancestor should be Document"
        assert isinstance(captured_path[1], BlockQuote), "Second ancestor should be BlockQuote"
        assert isinstance(captured_path[2], Paragraph), "Third ancestor should be Paragraph"
        assert isinstance(captured_path[3], Image), "Fourth node should be the Image itself"

        # Verify path is cleaned up after transformation
        assert len(context.node_path) == 0, "Node path should be empty after transformation completes"

    def test_context_aware_hook_can_check_ancestry(self):
        """Test that hooks can use node_path to make context-aware decisions.

        Example: Process images differently if they're inside a blockquote.
        """
        from all2md.ast import BlockQuote
        from all2md.transforms.pipeline import HookAwareVisitor

        # Create document with image inside blockquote and image outside
        doc = Document(children=[
            Paragraph(content=[
                Image(url="regular.png", alt_text="regular")
            ]),
            BlockQuote(children=[
                Paragraph(content=[
                    Image(url="quoted.png", alt_text="quoted")
                ])
            ])
        ])

        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        # Track which images are inside blockquotes
        images_in_blockquotes = []
        images_not_in_blockquotes = []

        def context_aware_image_hook(node, ctx):
            # Check if any ancestor is a BlockQuote
            is_in_blockquote = any(isinstance(ancestor, BlockQuote) for ancestor in ctx.node_path)

            if is_in_blockquote:
                images_in_blockquotes.append(node.url)
            else:
                images_not_in_blockquotes.append(node.url)

            return node

        manager.register_hook('image', context_aware_image_hook)

        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Verify the hook correctly identified which images are in blockquotes
        assert len(images_in_blockquotes) == 1, "Should find one image in blockquote"
        assert "quoted.png" in images_in_blockquotes, "quoted.png should be in blockquote"

        assert len(images_not_in_blockquotes) == 1, "Should find one image not in blockquote"
        assert "regular.png" in images_not_in_blockquotes, "regular.png should not be in blockquote"

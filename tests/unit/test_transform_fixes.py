#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for transform system bug fixes.

This module tests the specific fixes for issues found in code review:
1. Transform dependency ordering with conflicting priorities
2. Pipeline transform order preservation
3. HookContext.document staleness
4. HookAwareVisitor ancestry path updates
"""

import pytest

from all2md.ast import Document, Heading, Image, Paragraph, Text
from all2md.ast.transforms import NodeTransformer
from all2md.transforms import (
    HookContext,
    HookManager,
    Pipeline,
    TransformMetadata,
    TransformRegistry,
    render,
)
from all2md.transforms.pipeline import HookAwareVisitor


class TestFix1DependencyOrderingWithPriorities:
    """Tests for Fix 1: Dependency ordering respects topological constraints.

    Issue: After DFS topological sort, the code resorted by priority,
    which could violate dependencies when priorities conflict.

    Fix: Use Kahn's algorithm with priority as tiebreaker only among
    zero-indegree nodes.
    """

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        reg = TransformRegistry()
        reg.clear()
        reg._initialized = True
        return reg

    def test_dependencies_override_priorities(self, registry):
        """Test that dependencies are respected even with conflicting priorities.

        If B depends on A, then A must run before B regardless of priorities.
        Even if B has priority 50 and A has priority 200, order must be [A, B].
        """

        class TransformA(NodeTransformer):
            pass

        class TransformB(NodeTransformer):
            pass

        class TransformC(NodeTransformer):
            pass

        # Create chain: C depends on B, B depends on A
        # But give them conflicting priorities: C=50, B=100, A=200
        metadata_a = TransformMetadata(
            name="a",
            description="Transform A",
            transformer_class=TransformA,
            priority=200,  # Highest priority (runs last if no deps)
        )
        metadata_b = TransformMetadata(
            name="b",
            description="Transform B",
            transformer_class=TransformB,
            dependencies=["a"],
            priority=100,  # Medium priority
        )
        metadata_c = TransformMetadata(
            name="c",
            description="Transform C",
            transformer_class=TransformC,
            dependencies=["b"],
            priority=50,  # Lowest priority (runs first if no deps)
        )

        registry.register(metadata_a)
        registry.register(metadata_b)
        registry.register(metadata_c)

        # Request C - should get A, B, C in dependency order
        # NOT C, B, A which would be priority order
        ordered = registry.resolve_dependencies(["c"])
        assert ordered == ["a", "b", "c"], (
            "Dependencies must be respected regardless of priorities"
        )

    def test_priority_respected_among_independent_transforms(self, registry):
        """Test that priority is used as tiebreaker for independent transforms."""

        class TransformA(NodeTransformer):
            pass

        class TransformB(NodeTransformer):
            pass

        class TransformC(NodeTransformer):
            pass

        # Create independent transforms with different priorities
        metadata_a = TransformMetadata(
            name="a",
            description="Transform A",
            transformer_class=TransformA,
            priority=200,
        )
        metadata_b = TransformMetadata(
            name="b",
            description="Transform B",
            transformer_class=TransformB,
            priority=100,
        )
        metadata_c = TransformMetadata(
            name="c",
            description="Transform C",
            transformer_class=TransformC,
            priority=50,
        )

        registry.register(metadata_a)
        registry.register(metadata_b)
        registry.register(metadata_c)

        # All independent - should be ordered by priority
        ordered = registry.resolve_dependencies(["a", "b", "c"])
        assert ordered == ["c", "b", "a"], (
            "Independent transforms should be ordered by priority (lower first)"
        )


class TestFix2TransformOrderPreservation:
    """Tests for Fix 2: Pipeline preserves user-provided transform order.

    Issue: Instances were collected first, then all named transforms appended,
    losing interleaving like [instanceA, "T1", instanceB].

    Fix: Process transforms in order, expanding named transforms in place
    while maintaining deduplication.
    """

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        reg = TransformRegistry()
        reg.clear()
        reg._initialized = True
        return reg

    def test_mixed_transforms_preserve_order(self, registry):
        """Test that mixed instance and named transforms preserve interleaving."""

        class AddPrefixA(NodeTransformer):
            """Transform that adds prefix A to text."""

            def visit_text(self, node):
                return Text(
                    content=f"A{node.content}",
                    metadata=node.metadata.copy(),
                    source_location=node.source_location,
                )

        class AddPrefixB(NodeTransformer):
            """Transform that adds prefix B to text."""

            def visit_text(self, node):
                return Text(
                    content=f"B{node.content}",
                    metadata=node.metadata.copy(),
                    source_location=node.source_location,
                )

        class AddSuffix1(NodeTransformer):
            """Transform that adds suffix 1 to text."""

            def visit_text(self, node):
                return Text(
                    content=f"{node.content}1",
                    metadata=node.metadata.copy(),
                    source_location=node.source_location,
                )

        class AddSuffix2(NodeTransformer):
            """Transform that adds suffix 2 to text."""

            def visit_text(self, node):
                return Text(
                    content=f"{node.content}2",
                    metadata=node.metadata.copy(),
                    source_location=node.source_location,
                )

        # Register named transforms
        registry.register(
            TransformMetadata(
                name="add-prefix-a",
                description="Add prefix A",
                transformer_class=AddPrefixA,
            )
        )
        registry.register(
            TransformMetadata(
                name="add-prefix-b",
                description="Add prefix B",
                transformer_class=AddPrefixB,
            )
        )

        # Mix instances and named transforms
        # Expected order: prefix A, suffix 1, prefix B, suffix 2
        transforms = [
            "add-prefix-a",  # Named transform
            AddSuffix1(),  # Instance
            "add-prefix-b",  # Named transform
            AddSuffix2(),  # Instance
        ]

        # Create pipeline and resolve transforms
        pipeline = Pipeline(transforms=transforms)
        resolved = pipeline._resolve_transforms()

        # Should have 4 transforms in the specified order
        assert len(resolved) == 4

        # Verify we have the right types in order
        assert isinstance(resolved[0], AddPrefixA), "First should be AddPrefixA"
        assert isinstance(resolved[1], AddSuffix1), "Second should be AddSuffix1"
        assert isinstance(resolved[2], AddPrefixB), "Third should be AddPrefixB"
        assert isinstance(resolved[3], AddSuffix2), "Fourth should be AddSuffix2"


class TestFix3ContextDocumentStaleness:
    """Tests for Fix 3: HookContext.document is updated after modifications.

    Issue: context.document was set once and never updated after hooks/transforms
    modified the document, causing hooks to see stale state.

    Fix: Update context.document after every operation that returns a new Document.
    """

    def test_hooks_see_updated_document_after_transform(self):
        """Test that hooks see updated document after transforms modify it."""
        from all2md.transforms import apply

        # Create document
        original_doc = Document(
            children=[Paragraph(content=[Image(url="test.png", alt_text="test")])],
            metadata={"count": 0},
        )

        # Transform that removes images
        class RemoveImagesTransform(NodeTransformer):
            def visit_image(self, node):
                return None

        # Hook that checks context.document
        images_in_context_doc = []

        def check_context_doc(doc, context):
            # Count images in context.document
            # After RemoveImagesTransform, context.document should have no images
            count = 0
            for child in context.document.children:
                if hasattr(child, "content"):
                    for item in child.content:
                        if isinstance(item, Image):
                            count += 1
            images_in_context_doc.append(count)
            return doc

        # Apply transform, then check in pre_render hook
        apply(
            original_doc,
            transforms=[RemoveImagesTransform()],
            hooks={"pre_render": [check_context_doc]},
        )

        # Hook should have seen 0 images because context.document was updated
        # after the transform
        assert images_in_context_doc == [0], (
            "pre_render hook should see updated document with images removed"
        )

    def test_element_hooks_see_updated_document(self):
        """Test that element hooks see document updated by previous hooks."""
        # Create document
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Body")]),
            ],
            metadata={},
        )

        # Tracking what hooks see
        doc_child_counts = []

        # Hook that modifies document by adding a paragraph
        def add_paragraph_hook(doc_node, context):
            # Add a new paragraph to the document
            new_doc = Document(
                children=doc_node.children
                + [Paragraph(content=[Text(content="Added")])],
                metadata=doc_node.metadata.copy(),
            )
            return new_doc

        # Hook that checks document state
        def check_document_hook(node, context):
            # Record how many children the context.document has
            doc_child_counts.append(len(context.document.children))
            return node

        # Apply hooks
        render(
            doc,
            hooks={
                "pre_render": [add_paragraph_hook],
                "text": [check_document_hook],  # Element hook runs after pre_render
            },
        )

        # All text element hooks should see the updated document with 3 children
        # (2 original + 1 added by pre_render hook)
        assert all(
            count == 3 for count in doc_child_counts
        ), "All element hooks should see updated document"


class TestFix4NodePathWithReplacedNodes:
    """Tests for Fix 4: HookAwareVisitor updates node_path when hook replaces node.

    Issue: If a hook returns a different node, the code continues with the new node
    but node_path still contains the original node, giving descendants incorrect
    ancestry.

    Fix: After hook execution, if node was replaced, update top of node_path.
    """

    def test_descendants_see_replaced_parent_in_path(self):
        """Test that descendants see replaced parent node in their ancestry."""
        from all2md.ast import Link

        # Create document: Doc > Para > Link > Text
        doc = Document(
            children=[
                Paragraph(
                    content=[Link(url="http://example.com", content=[Text(content="link")])]
                )
            ]
        )

        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        # Track what text hook sees in its path
        link_in_path = []

        def replace_link_hook(node, ctx):
            """Hook that replaces Link node with a different Link."""
            new_link = Link(
                url="http://replaced.com",
                content=node.content,
                title="replaced",
                metadata=node.metadata.copy(),
                source_location=node.source_location,
            )
            return new_link

        def check_parent_link_hook(node, ctx):
            """Hook that checks if parent Link in path is the replaced one."""
            # Find Link in path
            for ancestor in ctx.node_path:
                if isinstance(ancestor, Link):
                    link_in_path.append(ancestor.url)
            return node

        manager.register_hook("link", replace_link_hook)
        manager.register_hook("text", check_parent_link_hook)

        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Text hook should see the REPLACED link in its ancestry
        assert len(link_in_path) == 1
        assert link_in_path[0] == "http://replaced.com", (
            "Descendant should see replaced parent node in path, not original"
        )

    def test_multiple_replacements_in_chain(self):
        """Test that multiple node replacements in ancestry are all visible."""
        from all2md.ast import Emphasis

        # Create doc: Doc > Para > Emphasis > Text
        doc = Document(
            children=[
                Paragraph(
                    content=[Emphasis(content=[Text(content="emphasized text")])]
                )
            ]
        )

        manager = HookManager()
        context = HookContext(document=doc, metadata={}, shared={})

        # Track modifications
        modifications = []

        def replace_paragraph_hook(node, ctx):
            """Replace paragraph with modified one."""
            modifications.append("para_replaced")
            new_para = Paragraph(
                content=node.content,
                metadata={"replaced": "paragraph"},
                source_location=node.source_location,
            )
            return new_para

        def replace_emphasis_hook(node, ctx):
            """Replace emphasis with modified one."""
            modifications.append("emphasis_replaced")
            new_emphasis = Emphasis(
                content=node.content,
                metadata={"replaced": "emphasis"},
                source_location=node.source_location,
            )
            return new_emphasis

        def check_ancestry_hook(node, ctx):
            """Check that text sees both replaced ancestors."""
            # Check paragraph in path has the replaced metadata
            for ancestor in ctx.node_path:
                if isinstance(ancestor, Paragraph):
                    assert "replaced" in ancestor.metadata
                    assert ancestor.metadata["replaced"] == "paragraph"
                    modifications.append("para_seen_correctly")
                elif isinstance(ancestor, Emphasis):
                    assert "replaced" in ancestor.metadata
                    assert ancestor.metadata["replaced"] == "emphasis"
                    modifications.append("emphasis_seen_correctly")
            return node

        manager.register_hook("paragraph", replace_paragraph_hook)
        manager.register_hook("emphasis", replace_emphasis_hook)
        manager.register_hook("text", check_ancestry_hook)

        visitor = HookAwareVisitor(manager, context)
        visitor.transform(doc)

        # Verify all hooks ran and descendants saw replaced ancestors
        assert "para_replaced" in modifications
        assert "emphasis_replaced" in modifications
        assert "para_seen_correctly" in modifications
        assert "emphasis_seen_correctly" in modifications


# New tests for code review fixes (Issues 5-7)

class TestFix5TimezoneAwareTimestamps:
    """Tests for Fix 5: Timezone-aware timestamps in AddConversionTimestampTransform."""

    def test_iso_timestamp_includes_utc_timezone(self):
        """Test that ISO timestamps include UTC timezone information."""
        from all2md.transforms.builtin import AddConversionTimestampTransform

        doc = Document(children=[])
        transform = AddConversionTimestampTransform(format="iso")
        result = transform.transform(doc)

        timestamp = result.metadata['conversion_timestamp']

        # ISO 8601 UTC timestamps should end with +00:00 or Z
        assert '+00:00' in timestamp or timestamp.endswith('Z'), \
            f"Timestamp should include UTC timezone: {timestamp}"

    def test_unix_timestamp_is_utc_based(self):
        """Test that Unix timestamps are UTC-based."""
        from datetime import datetime, timezone

        from all2md.transforms.builtin import AddConversionTimestampTransform

        doc = Document(children=[])
        transform = AddConversionTimestampTransform(format="unix")

        before = int(datetime.now(timezone.utc).timestamp())
        result = transform.transform(doc)
        after = int(datetime.now(timezone.utc).timestamp())

        unix_ts = int(result.metadata['conversion_timestamp'])

        # Timestamp should be within reasonable range of current UTC time
        assert before <= unix_ts <= after + 1, \
            "Unix timestamp should be within UTC time range"

    def test_arbitrary_strftime_format_works(self):
        """Test that arbitrary strftime patterns work (metadata allows any format)."""
        from all2md.transforms.builtin import AddConversionTimestampTransform

        doc = Document(children=[])

        # Test various strftime patterns
        test_formats = [
            ("%Y", 4),  # Just year
            ("%Y-%m", 7),  # Year-month
            ("%Y-%m-%d", 10),  # Date only
            ("%H:%M", 5),  # Time only
        ]

        for format_str, expected_min_length in test_formats:
            transform = AddConversionTimestampTransform(format=format_str)
            result = transform.transform(doc)
            timestamp = result.metadata['conversion_timestamp']
            assert len(timestamp) >= expected_min_length, \
                f"Format {format_str} should produce valid timestamp, got: {timestamp}"


class TestFix6AddAttachmentFootnotesRegistration:
    """Tests for Fix 6: AddAttachmentFootnotesTransform registration and export."""

    def test_transform_is_registered_in_registry(self):
        """Test that AddAttachmentFootnotesTransform is registered."""
        from all2md.transforms import registry

        # Ensure registry is initialized (in case previous tests cleared it)
        registry._ensure_initialized()

        registered_transforms = registry.list_transforms()
        assert "add-attachment-footnotes" in registered_transforms, \
            "AddAttachmentFootnotesTransform should be registered as 'add-attachment-footnotes'"

    def test_metadata_is_exported(self):
        """Test that ADD_ATTACHMENT_FOOTNOTES_METADATA is exported."""
        from all2md.transforms import ADD_ATTACHMENT_FOOTNOTES_METADATA

        assert ADD_ATTACHMENT_FOOTNOTES_METADATA is not None
        assert ADD_ATTACHMENT_FOOTNOTES_METADATA.name == "add-attachment-footnotes"

    def test_transform_can_be_instantiated_via_metadata(self):
        """Test that transform can be instantiated via metadata."""
        from all2md.transforms import ADD_ATTACHMENT_FOOTNOTES_METADATA

        instance = ADD_ATTACHMENT_FOOTNOTES_METADATA.create_instance()

        assert instance is not None
        assert instance.section_title == "Attachments"
        assert instance.add_definitions_for_images is True
        assert instance.add_definitions_for_links is True


class TestFix7CentralizedBoilerplatePatterns:
    """Tests for Fix 7: Centralized boilerplate patterns across all locations."""

    def test_constant_has_all_six_patterns(self):
        """Test that DEFAULT_BOILERPLATE_PATTERNS contains all 6 patterns."""
        from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS

        assert len(DEFAULT_BOILERPLATE_PATTERNS) == 6, \
            f"DEFAULT_BOILERPLATE_PATTERNS should have 6 patterns, got {len(DEFAULT_BOILERPLATE_PATTERNS)}"

    def test_transform_uses_centralized_patterns(self):
        """Test that RemoveBoilerplateTextTransform uses centralized patterns."""
        from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        transform = RemoveBoilerplateTextTransform()
        assert transform.patterns == DEFAULT_BOILERPLATE_PATTERNS, \
            "Transform should use centralized DEFAULT_BOILERPLATE_PATTERNS"

    def test_options_uses_centralized_patterns(self):
        """Test that RemoveBoilerplateOptions uses centralized patterns."""
        from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS
        from all2md.transforms.options import RemoveBoilerplateOptions

        options = RemoveBoilerplateOptions()
        assert options.patterns == DEFAULT_BOILERPLATE_PATTERNS, \
            "Options should use centralized DEFAULT_BOILERPLATE_PATTERNS"

    def test_metadata_uses_centralized_patterns(self):
        """Test that REMOVE_BOILERPLATE_METADATA uses centralized patterns."""
        from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS
        from all2md.transforms import REMOVE_BOILERPLATE_METADATA

        metadata = REMOVE_BOILERPLATE_METADATA
        patterns_param = metadata.parameters.get('patterns')

        assert patterns_param is not None, "Metadata should have 'patterns' parameter"
        assert patterns_param.default == DEFAULT_BOILERPLATE_PATTERNS, \
            "Metadata default should use centralized patterns"

    def test_all_locations_use_identical_patterns(self):
        """Test that all three locations use the exact same pattern list."""
        from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS
        from all2md.transforms import REMOVE_BOILERPLATE_METADATA
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform
        from all2md.transforms.options import RemoveBoilerplateOptions

        # Get patterns from all three locations
        transform_patterns = RemoveBoilerplateTextTransform().patterns
        options_patterns = RemoveBoilerplateOptions().patterns
        metadata_patterns = REMOVE_BOILERPLATE_METADATA.parameters['patterns'].default

        # All should be identical to the centralized constant
        assert transform_patterns == DEFAULT_BOILERPLATE_PATTERNS
        assert options_patterns == DEFAULT_BOILERPLATE_PATTERNS
        assert metadata_patterns == DEFAULT_BOILERPLATE_PATTERNS

    def test_transform_removes_all_default_patterns(self):
        """Test that transform removes all 6 default boilerplate patterns."""
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        doc = Document(children=[
            Paragraph(content=[Text(content="CONFIDENTIAL")]),
            Paragraph(content=[Text(content="Page 1 of 10")]),
            Paragraph(content=[Text(content="Internal Use Only")]),
            Paragraph(content=[Text(content="[DRAFT]")]),
            Paragraph(content=[Text(content="Copyright 2025")]),
            Paragraph(content=[Text(content="Printed on 2025-01-15")]),
            Paragraph(content=[Text(content="Normal text to keep")]),
        ])

        transform = RemoveBoilerplateTextTransform()
        result = transform.transform(doc)

        # Should only have the normal text paragraph
        assert len(result.children) == 1
        assert result.children[0].content[0].content == "Normal text to keep"

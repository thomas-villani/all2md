# Renderer Implementation Patterns

This document explains the best practices for implementing visitor methods in all2md renderer plugins, especially for handling AST node types that your format doesn't natively support.

## The Challenge

When implementing a renderer plugin, you must implement visitor methods for ALL AST node types, even if your target format doesn't support them. The `NodeVisitor` base class requires these methods to provide complete AST traversal.

## Best Practices

### 1. Formatting Nodes (Extract Content)

For nodes that represent formatting your format doesn't support (bold, italic, strikethrough, underline, superscript, subscript), **extract and render the text content**:

```python
def visit_strikethrough(self, node: Strikethrough) -> None:
    """Render a Strikethrough node.

    SimpleDoc doesn't have strikethrough formatting, so we extract
    and render the text content without the formatting.

    Parameters
    ----------
    node : Strikethrough
        Strikethrough to render

    """
    content = self._render_inline_content(node.content)
    self._output.append(content)
```

**Why:** This preserves the text content even if the formatting is lost. Users can still read the document.

### 2. Unsupported Elements (Skip or Simplify)

For elements your format truly doesn't support (HTML blocks, footnotes, math notation), you have options:

**Option A: Skip entirely (use `pass`)**

```python
def visit_html_block(self, node: HTMLBlock) -> None:
    """Render an HTMLBlock node.

    SimpleDoc doesn't support HTML blocks, so we skip them.

    Parameters
    ----------
    node : HTMLBlock
        HTML block to render

    """
    pass
```

**Option B: Provide simplified representation**

```python
def visit_definition_list(self, node: DefinitionList) -> None:
    """Render a DefinitionList node.

    SimpleDoc doesn't have native definition list syntax,
    so we render it as a simplified text representation.

    Parameters
    ----------
    node : DefinitionList
        Definition list to render

    """
    for i, (term, descriptions) in enumerate(node.items):
        term_content = self._render_inline_content(term.content)
        self._output.append(f"Term: {term_content}\n")
        for desc in descriptions:
            self._output.append("  Definition: ")
            for child in desc.content:
                child.accept(self)
            self._output.append("\n")
```

**Why:** Users appreciate when content is preserved in some form, even if imperfect.

### 3. Structural Nodes (Handled Elsewhere)

For nodes that are handled by their parent (table cells, table rows, list items in some cases), use `pass` but **document why**:

```python
def visit_table_cell(self, node: TableCell) -> None:
    """Render a TableCell node.

    This is handled by visit_table, so this method is a no-op.
    The table visitor directly accesses cell content.

    Parameters
    ----------
    node : TableCell
        Table cell to render

    """
    pass
```

**Why:** Makes it clear this isn't an oversight, but an architectural decision.

## Documentation Requirements

For EVERY visitor method, include:

1. **Clear docstring** explaining what happens
2. **NumPy-style parameters section** documenting the node parameter
3. **Explanation of WHY** the node is handled this way
4. **Return type annotation** (usually `-> None` for visitors)

## Testing Considerations

When writing tests, verify that:

1. **Formatting is preserved as text**: `Strikethrough("test")` → `"test"`
2. **Unsupported elements don't crash**: Rendering a footnote doesn't raise errors
3. **Complex documents work**: AST with all node types renders without errors

## Example Test

```python
def test_unsupported_formatting_preserves_content():
    """Test that unsupported formatting still renders text content."""
    from all2md.ast import Document, Paragraph, Strikethrough, Text

    doc = Document(children=[
        Paragraph(content=[
            Strikethrough(content=[Text(content="crossed out")])
        ])
    ])

    renderer = SimpleDocRenderer()
    output = renderer.render_to_string(doc)

    # Content should be preserved even without strikethrough
    assert "crossed out" in output
```

## Summary: The Three Categories

| Category | Action | Example Nodes | Return Value |
|----------|--------|---------------|--------------|
| **Formatting** | Extract content | Strikethrough, Underline, Superscript, Subscript | None |
| **Unsupported** | Skip or simplify | HTMLBlock, Footnotes, Math | None |
| **Structural** | Parent handles it | TableCell, DefinitionTerm | None |

## Key Takeaway

**Every visitor method MUST exist and be properly documented**, even if it's just `pass`. This makes your plugin:
- ✅ Complete and production-ready
- ✅ Educational for other developers
- ✅ Robust (no crashes on unexpected node types)
- ✅ Clear about what's supported and what isn't

---

See `src/all2md_simpledoc/renderer.py` for a complete working example following these patterns.

#!/usr/bin/env python3
"""Round-trip a document through the AST's JSON form -- an LLM-friendly interchange.

all2md's AST serializes to plain JSON and back. That JSON is a stable, inspectable
representation of a document's *structure* (headings, paragraphs, tables, links,
images, ...) -- handy for:

- handing document structure to an LLM as JSON instead of prose,
- storing/diffing a parsed document,
- editing the tree programmatically, then rendering to any format.

Pipeline demonstrated:

    file --to_ast--> Document --ast_to_json--> JSON string
    JSON string --json_to_ast--> Document --from_ast--> Markdown / HTML / ...

Usage:
    python ast_json_roundtrip.py <document> [output_format]
    python ast_json_roundtrip.py ../../tests/fixtures/documents/basic.docx
    python ast_json_roundtrip.py report.pdf html
"""

from __future__ import annotations

import json
import sys

from all2md import from_ast, to_ast
from all2md.ast import Heading
from all2md.ast.serialization import ast_to_json, json_to_ast
from all2md.ast.transforms import extract_nodes
from all2md.ast.utils import extract_text


def main() -> int:
    """Parse to AST, serialize to JSON, deserialize, and render back out."""
    if len(sys.argv) < 2:
        print("Usage: python ast_json_roundtrip.py <document> [output_format]")
        return 1

    source = sys.argv[1]
    output_format = sys.argv[2] if len(sys.argv) > 2 else "markdown"

    # 1. Parse the document to an AST Document.
    print(f"Parsing {source} ...")
    doc = to_ast(source)

    # 2. Serialize the AST to JSON. This is the interchange format -- it is plain,
    #    schema-validated JSON you could store, diff, or hand to an LLM.
    json_str = ast_to_json(doc, indent=2)
    print(f"Serialized AST to JSON ({len(json_str):,} bytes).")

    # Peek at the top-level structure so the JSON shape is visible.
    parsed = json.loads(json_str)
    print(f"  Root node type: {parsed.get('node_type')}  (schema {parsed.get('schema_version')})")
    print(f"  Top-level children: {len(parsed.get('children', []))}")

    # 3. Deserialize the JSON back into an AST Document. Round-trip complete.
    doc2 = json_to_ast(json_str)

    # 4. The reconstructed tree is fully usable -- inspect it, then render it.
    headings = extract_nodes(doc2, Heading)
    print(f"\nReconstructed document has {len(headings)} heading(s):")
    for h in headings[:10]:
        print(f"  {'#' * h.level} {extract_text(h)}")

    output = from_ast(doc2, output_format)
    print(f"\nRendered reconstructed AST to {output_format}:")
    print("=" * 70)
    print(output[:600] if isinstance(output, str) else f"<{len(output)} bytes of binary output>")

    return 0


if __name__ == "__main__":
    sys.exit(main())

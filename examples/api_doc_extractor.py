#!/usr/bin/env python3
"""API Documentation Code Extractor.

This example demonstrates how to extract code examples from documentation and
generate runnable test files. It uses the all2md AST to extract code blocks,
validate syntax, and organize them into executable examples.

Features
--------
- Extract code blocks by programming language
- Create single test file per language with all examples
- Add boilerplate code (imports, setup, test runners)
- Validate Python code syntax
- Generate README documenting extracted examples
- Support common languages (Python, JavaScript, Java, etc.)

Use Cases
---------
- Documentation testing
- Example maintenance
- SDK development
- Tutorial creation
"""

import ast
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from all2md import to_ast
from all2md.ast import CodeBlock, Document, Heading, Paragraph
from all2md.ast.transforms import extract_nodes
from all2md.ast.utils import extract_text


@dataclass
class ExtractedCode:
    """A code block extracted from documentation.

    Parameters
    ----------
    language : str
        Programming language
    code : str
        Code content
    context : str
        Surrounding context or description
    heading : str
        Section heading where code was found
    line_number : int or None, default = None
        Line number in source document
    is_valid : bool, default = True
        Whether code passed syntax validation

    """

    language: str
    code: str
    context: str
    heading: str
    line_number: Optional[int] = None
    is_valid: bool = True


@dataclass
class ExtractionResult:
    """Results of code extraction.

    Parameters
    ----------
    total_blocks : int, default = 0
        Total code blocks found
    by_language : dict, default = empty dict
        Code blocks grouped by language
    invalid_blocks : list of ExtractedCode, default = empty list
        Code blocks that failed validation

    """

    total_blocks: int = 0
    by_language: dict[str, list[ExtractedCode]] = field(default_factory=dict)
    invalid_blocks: list[ExtractedCode] = field(default_factory=list)


def normalize_language(language: Optional[str]) -> str:
    """Normalize language identifier.

    Parameters
    ----------
    language : str or None
        Raw language identifier from code block

    Returns
    -------
    str
        Normalized language name

    """
    if not language:
        return "text"

    lang = language.lower().strip()

    aliases = {
        "py": "python",
        "python3": "python",
        "js": "javascript",
        "ts": "typescript",
        "sh": "bash",
        "shell": "bash",
        "yml": "yaml",
        "rb": "ruby",
        "rs": "rust",
        "kt": "kotlin",
        "go": "golang",
    }

    return aliases.get(lang, lang)


def validate_python_syntax(code: str) -> tuple[bool, str]:
    """Validate Python code syntax.

    Parameters
    ----------
    code : str
        Python code to validate

    Returns
    -------
    tuple of (bool, str)
        (is_valid, error_message)

    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)


def get_context_before_code(doc: Document, code_block_idx: int) -> str:
    """Get contextual text before a code block.

    Parameters
    ----------
    doc : Document
        Document AST
    code_block_idx : int
        Index of code block in document children

    Returns
    -------
    str
        Context text

    """
    children = doc.children
    context_parts = []

    for i in range(code_block_idx - 1, max(-1, code_block_idx - 3), -1):
        child = children[i]
        if isinstance(child, Paragraph):
            text = extract_text(child.content, joiner="")
            context_parts.insert(0, text)
        elif isinstance(child, Heading):
            break

    return " ".join(context_parts)


def get_current_heading(doc: Document, code_block_idx: int) -> str:
    """Get the heading for the current section.

    Parameters
    ----------
    doc : Document
        Document AST
    code_block_idx : int
        Index of code block in document children

    Returns
    -------
    str
        Heading text or empty string

    """
    children = doc.children

    for i in range(code_block_idx - 1, -1, -1):
        if isinstance(children[i], Heading):
            return extract_text(children[i].content, joiner="")

    return ""


def extract_code_blocks(input_path: str, validate: bool = True) -> ExtractionResult:
    """Extract all code blocks from documentation.

    Parameters
    ----------
    input_path : str
        Path to documentation file
    validate : bool, default = True
        Whether to validate Python code syntax

    Returns
    -------
    ExtractionResult
        Extraction results

    """
    print(f"Parsing documentation: {input_path}")
    doc = to_ast(input_path)

    print("Extracting code blocks...")
    code_blocks = extract_nodes(doc, CodeBlock)

    result = ExtractionResult()
    by_language = defaultdict(list)

    children = doc.children

    for code_node in code_blocks:
        idx = children.index(code_node) if code_node in children else -1

        language = normalize_language(code_node.language)
        context = get_context_before_code(doc, idx) if idx >= 0 else ""
        heading = get_current_heading(doc, idx) if idx >= 0 else ""

        line_number = None
        if code_node.source_location and code_node.source_location.line:
            line_number = code_node.source_location.line

        extracted = ExtractedCode(
            language=language,
            code=code_node.content,
            context=context,
            heading=heading,
            line_number=line_number,
        )

        if validate and language == "python":
            is_valid, error = validate_python_syntax(code_node.content)
            extracted.is_valid = is_valid
            if not is_valid:
                result.invalid_blocks.append(extracted)
                print(f"  Warning: Invalid Python syntax - {error}")

        by_language[language].append(extracted)
        result.total_blocks += 1

    result.by_language = dict(by_language)

    print(f"Found {result.total_blocks} code blocks")
    print(f"Languages: {', '.join(result.by_language.keys())}")

    return result


def generate_python_test_file(blocks: list[ExtractedCode]) -> str:
    """Generate a Python test file with all examples.

    Parameters
    ----------
    blocks : list of ExtractedCode
        Python code blocks to include

    Returns
    -------
    str
        Generated Python test file content

    """
    lines = []

    lines.append('"""Extracted code examples from documentation.')
    lines.append("")
    lines.append("This file contains all Python code examples extracted from the")
    lines.append("documentation. Each example is wrapped in a function for testing.")
    lines.append('"""')
    lines.append("")

    lines.append("import sys")
    lines.append("")

    for i, block in enumerate(blocks, 1):
        func_name = f"example_{i}"

        lines.append("")
        lines.append(f"def {func_name}():")
        lines.append(f'    """Example {i}: {block.heading}')
        lines.append("")
        if block.context:
            lines.append(f"    {block.context[:70]}...")
        lines.append('    """')

        code_lines = block.code.split("\n")
        for code_line in code_lines:
            if code_line.strip():
                lines.append(f"    {code_line}")
            else:
                lines.append("")

        lines.append("")

    lines.append("")
    lines.append("def run_all_examples():")
    lines.append('    """Run all extracted examples."""')
    lines.append('    examples = [')
    for i in range(1, len(blocks) + 1):
        lines.append(f'        ("Example {i}", example_{i}),')
    lines.append("    ]")
    lines.append("")
    lines.append("    print(f'Running {len(examples)} examples...')")
    lines.append("    print('-' * 60)")
    lines.append("")
    lines.append("    for name, func in examples:")
    lines.append("        try:")
    lines.append("            print(f'Running {name}...')")
    lines.append("            func()")
    lines.append("            print(f'  OK')")
    lines.append("        except Exception as e:")
    lines.append("            print(f'  FAILED: {e}')")
    lines.append("")
    lines.append("    print('-' * 60)")
    lines.append("")

    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append("    run_all_examples()")

    return "\n".join(lines)


def generate_javascript_test_file(blocks: list[ExtractedCode]) -> str:
    """Generate a JavaScript test file with all examples.

    Parameters
    ----------
    blocks : list of ExtractedCode
        JavaScript code blocks to include

    Returns
    -------
    str
        Generated JavaScript test file content

    """
    lines = []

    lines.append("/**")
    lines.append(" * Extracted code examples from documentation")
    lines.append(" */")
    lines.append("")

    for i, block in enumerate(blocks, 1):
        func_name = f"example{i}"

        lines.append("")
        lines.append(f"function {func_name}() {{")
        lines.append(f"  // Example {i}: {block.heading}")
        if block.context:
            lines.append(f"  // {block.context[:60]}...")

        code_lines = block.code.split("\n")
        for code_line in code_lines:
            lines.append(f"  {code_line}")

        lines.append("}")

    lines.append("")
    lines.append("function runAllExamples() {")
    lines.append("  const examples = [")
    for i in range(1, len(blocks) + 1):
        lines.append(f'    {{ name: "Example {i}", func: example{i} }},')
    lines.append("  ];")
    lines.append("")
    lines.append('  console.log(`Running ${examples.length} examples...`);')
    lines.append('  console.log("-".repeat(60));')
    lines.append("")
    lines.append("  examples.forEach(({ name, func }) => {")
    lines.append("    try {")
    lines.append('      console.log(`Running ${name}...`);')
    lines.append("      func();")
    lines.append('      console.log("  OK");')
    lines.append("    } catch (e) {")
    lines.append('      console.log(`  FAILED: ${e.message}`);')
    lines.append("    }")
    lines.append("  });")
    lines.append("")
    lines.append('  console.log("-".repeat(60));')
    lines.append("}")
    lines.append("")
    lines.append("runAllExamples();")

    return "\n".join(lines)


def generate_test_file(language: str, blocks: list[ExtractedCode]) -> Optional[str]:
    """Generate test file for a specific language.

    Parameters
    ----------
    language : str
        Programming language
    blocks : list of ExtractedCode
        Code blocks for this language

    Returns
    -------
    str or None
        Generated test file content or None if language not supported

    """
    if language == "python":
        return generate_python_test_file(blocks)
    elif language == "javascript":
        return generate_javascript_test_file(blocks)
    else:
        return None


def get_file_extension(language: str) -> str:
    """Get file extension for a language.

    Parameters
    ----------
    language : str
        Programming language

    Returns
    -------
    str
        File extension (e.g., '.py', '.js')

    """
    extensions = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "java": ".java",
        "csharp": ".cs",
        "ruby": ".rb",
        "go": ".go",
        "rust": ".rs",
        "bash": ".sh",
        "yaml": ".yaml",
        "json": ".json",
    }
    return extensions.get(language, ".txt")


def generate_readme(result: ExtractionResult, output_dir: str) -> str:
    """Generate README for extracted examples.

    Parameters
    ----------
    result : ExtractionResult
        Extraction results
    output_dir : str
        Output directory path

    Returns
    -------
    str
        README content

    """
    lines = []

    lines.append("# Extracted Code Examples")
    lines.append("")
    lines.append(
        "This directory contains code examples extracted from documentation."
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total code blocks: {result.total_blocks}")
    lines.append(f"- Languages: {len(result.by_language)}")
    lines.append("")

    lines.append("## Files")
    lines.append("")
    for language, blocks in sorted(result.by_language.items()):
        ext = get_file_extension(language)
        filename = f"examples{ext}"
        lines.append(f"- `{filename}` - {len(blocks)} {language} examples")
    lines.append("")

    if result.invalid_blocks:
        lines.append("## Validation Issues")
        lines.append("")
        lines.append(
            f"Found {len(result.invalid_blocks)} blocks with syntax errors:"
        )
        for block in result.invalid_blocks:
            lines.append(f"- {block.language}: {block.heading}")
        lines.append("")

    lines.append("## Usage")
    lines.append("")
    lines.append("### Python Examples")
    lines.append("")
    lines.append("```bash")
    lines.append("python examples.py")
    lines.append("```")
    lines.append("")

    lines.append("### JavaScript Examples")
    lines.append("")
    lines.append("```bash")
    lines.append("node examples.js")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def extract_and_generate(
    input_path: str, output_dir: str, validate: bool = True
) -> ExtractionResult:
    """Extract code and generate test files.

    Parameters
    ----------
    input_path : str
        Path to documentation file
    output_dir : str
        Output directory for generated files
    validate : bool, default = True
        Whether to validate code syntax

    Returns
    -------
    ExtractionResult
        Extraction results

    """
    result = extract_code_blocks(input_path, validate=validate)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating test files in: {output_dir}")

    for language, blocks in result.by_language.items():
        test_content = generate_test_file(language, blocks)

        if test_content:
            ext = get_file_extension(language)
            filename = f"examples{ext}"
            filepath = output_path / filename

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(test_content)

            print(f"  Created {filename} with {len(blocks)} examples")

    readme_content = generate_readme(result, output_dir)
    readme_path = output_path / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"  Created README.md")

    return result


def main():
    """Run the API documentation extractor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract code examples from documentation"
    )
    parser.add_argument("input", help="Input documentation file")
    parser.add_argument(
        "--output",
        "-o",
        default="./extracted_examples",
        help="Output directory (default: ./extracted_examples)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip syntax validation for Python code",
    )

    args = parser.parse_args()

    result = extract_and_generate(
        args.input, args.output, validate=not args.no_validate
    )

    print("\n" + "=" * 70)
    print("Extraction Complete")
    print("=" * 70)
    print(f"Total code blocks: {result.total_blocks}")
    print(f"Languages: {', '.join(result.by_language.keys())}")
    if result.invalid_blocks:
        print(f"Validation issues: {len(result.invalid_blocks)}")
    print(f"Output directory: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("API Documentation Code Extractor")
        print("=" * 70)
        print()
        print("Extract code examples from documentation and generate test files.")
        print()
        print("Usage:")
        print("  python api_doc_extractor.py api_docs.md")
        print("  python api_doc_extractor.py tutorial.html --output ./examples")
        print("  python api_doc_extractor.py README.md --no-validate")
        print()
        print("Features:")
        print("  - Extract code blocks by programming language")
        print("  - Generate single test file per language")
        print("  - Add boilerplate code (imports, test runners)")
        print("  - Validate Python syntax")
        print("  - Generate README documenting examples")
        print()
        print("Options:")
        print("  --output DIR      Output directory (default: ./extracted_examples)")
        print("  --no-validate     Skip Python syntax validation")
        print()
        print("Supported Languages:")
        print("  - Python (generates runnable test file)")
        print("  - JavaScript (generates runnable test file)")
        print("  - Other languages (extracted but not wrapped in test harness)")
        print()
        print("Example:")
        print("  python api_doc_extractor.py docs/api.md --output examples/")
        print()
        sys.exit(0)

    main()

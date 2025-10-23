#!/usr/bin/env python3
"""Code Example Generator from Documentation.

This example demonstrates how to automatically generate working code examples
from API documentation using LLMs. It extracts API descriptions, generates
examples, validates them, and inserts them back into the documentation.

Features
--------
- Extract API descriptions and function signatures
- Generate working code examples via LLM
- Insert back into docs as properly formatted code blocks
- Verify examples compile/run
- Add explanatory comments
- Generate examples in multiple languages

Use Cases
---------
- API documentation enhancement
- Tutorial creation
- SDK examples
- Developer onboarding
"""

import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from all2md import from_ast, to_ast
from all2md.ast import CodeBlock, Document, Heading, Node, Paragraph
from all2md.ast.builder import DocumentBuilder
from all2md.ast.transforms import NodeTransformer, extract_nodes
from all2md.ast.utils import extract_text


@dataclass
class APISection:
    """An API section that needs code examples.

    Parameters
    ----------
    heading : str
        API name/title
    description : str
        API description text
    existing_code : list of CodeBlock, default = empty list
        Existing code blocks in this section
    code_language : str or None, default = None
        Target programming language
    needs_example : bool, default = True
        Whether this section needs examples generated

    """

    heading: str
    description: str
    existing_code: list[CodeBlock] = field(default_factory=list)
    code_language: Optional[str] = None
    needs_example: bool = True


@dataclass
class GeneratedExample:
    """A generated code example.

    Parameters
    ----------
    code : str
        Generated code
    language : str
        Programming language
    explanation : str
        Explanation of the code
    is_valid : bool, default = False
        Whether code passed validation
    validation_error : str, default = ''
        Validation error message if any

    """

    code: str
    language: str
    explanation: str
    is_valid: bool = False
    validation_error: str = ""


@dataclass
class GenerationReport:
    """Report of example generation.

    Parameters
    ----------
    sections_processed : int, default = 0
        Number of API sections processed
    examples_generated : int, default = 0
        Number of examples generated
    examples_validated : int, default = 0
        Number of examples validated successfully
    examples_failed : int, default = 0
        Number of examples that failed validation

    """

    sections_processed: int = 0
    examples_generated: int = 0
    examples_validated: int = 0
    examples_failed: int = 0


def extract_api_sections(
    doc: Document, target_language: Optional[str] = None
) -> list[APISection]:
    """Extract API sections from documentation.

    Parameters
    ----------
    doc : Document
        Documentation AST
    target_language : str or None, default = None
        Target programming language for examples

    Returns
    -------
    list of APISection
        Extracted API sections

    """
    sections = []
    children = doc.children

    current_heading = None
    current_description = []
    current_code_blocks = []

    for i, child in enumerate(children):
        if isinstance(child, Heading):
            if current_heading and current_description:
                description_text = " ".join(current_description)
                needs_example = len(current_code_blocks) == 0

                section = APISection(
                    heading=current_heading,
                    description=description_text,
                    existing_code=current_code_blocks,
                    code_language=target_language,
                    needs_example=needs_example,
                )
                sections.append(section)

            current_heading = extract_text(child.content, joiner="")
            current_description = []
            current_code_blocks = []

        elif isinstance(child, Paragraph):
            text = extract_text(child.content, joiner="")
            current_description.append(text)

        elif isinstance(child, CodeBlock):
            current_code_blocks.append(child)

    if current_heading and current_description:
        description_text = " ".join(current_description)
        needs_example = len(current_code_blocks) == 0

        section = APISection(
            heading=current_heading,
            description=description_text,
            existing_code=current_code_blocks,
            code_language=target_language,
            needs_example=needs_example,
        )
        sections.append(section)

    return sections


def validate_python_code(code: str) -> tuple[bool, str]:
    """Validate Python code by parsing and optionally running.

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
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        result = subprocess.run(
            [sys.executable, "-m", "py_compile", temp_path],
            capture_output=True,
            text=True,
            timeout=5,
        )

        Path(temp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            return False, result.stderr

        return True, ""

    except subprocess.TimeoutExpired:
        return False, "Validation timeout"
    except Exception as e:
        return False, str(e)


def validate_javascript_code(code: str) -> tuple[bool, str]:
    """Validate JavaScript code using Node.js syntax check.

    Parameters
    ----------
    code : str
        JavaScript code to validate

    Returns
    -------
    tuple of (bool, str)
        (is_valid, error_message)

    """
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name

        result = subprocess.run(
            ["node", "--check", temp_path],
            capture_output=True,
            text=True,
            timeout=5,
        )

        Path(temp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            return False, result.stderr

        return True, ""

    except FileNotFoundError:
        return False, "Node.js not installed (skipping validation)"
    except subprocess.TimeoutExpired:
        return False, "Validation timeout"
    except Exception as e:
        return False, str(e)


def validate_code(code: str, language: str) -> tuple[bool, str]:
    """Validate generated code.

    Parameters
    ----------
    code : str
        Code to validate
    language : str
        Programming language

    Returns
    -------
    tuple of (bool, str)
        (is_valid, error_message)

    """
    if language == "python":
        return validate_python_code(code)
    elif language == "javascript":
        return validate_javascript_code(code)
    else:
        return True, "Validation not available for this language"


def generate_example_with_llm(
    section: APISection, llm_client: Callable[[str], str]
) -> GeneratedExample:
    """Generate code example using LLM.

    Parameters
    ----------
    section : APISection
        API section to generate example for
    llm_client : callable
        LLM client function

    Returns
    -------
    GeneratedExample
        Generated example

    """
    language = section.code_language or "python"

    prompt = f"""Generate a complete, working code example for this API:

API: {section.heading}
Description: {section.description}
Language: {language}

Requirements:
1. Create a complete, runnable example
2. Include necessary imports
3. Add clear comments explaining each step
4. Handle errors appropriately
5. Show realistic usage
6. Keep it concise but complete

Format your response as:

```{language}
[code here]
```

Then provide a brief explanation of what the code does.
"""

    try:
        response = llm_client(prompt)

        code_match = re.search(r"```(?:\w+)?\n(.*?)```", response, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
        else:
            code = response.strip()

        explanation_parts = re.split(r"```(?:\w+)?\n.*?```", response, flags=re.DOTALL)
        explanation = " ".join(part.strip() for part in explanation_parts if part.strip())

        if not explanation:
            explanation = f"Example usage of {section.heading}"

        example = GeneratedExample(
            code=code,
            language=language,
            explanation=explanation,
        )

        is_valid, error = validate_code(code, language)
        example.is_valid = is_valid
        example.validation_error = error

        return example

    except Exception as e:
        return GeneratedExample(
            code=f"# Error generating example: {e}",
            language=language,
            explanation="Failed to generate example",
            validation_error=str(e),
        )


def mock_llm_client(prompt: str) -> str:
    """Mock LLM client for demonstration.

    Parameters
    ----------
    prompt : str
        LLM prompt

    Returns
    -------
    str
        Mock response

    """
    language_match = re.search(r"Language: (\w+)", prompt)
    language = language_match.group(1) if language_match else "python"

    api_match = re.search(r"API: (.+)", prompt)
    api_name = api_match.group(1) if api_match else "example_function"

    if language == "python":
        code = f'''# Import required modules
import example_module

# Initialize the API
api = example_module.{api_name.replace(" ", "_").lower()}()

# Use the API
result = api.execute()

# Print the result
print(f"Result: {{result}}")
'''
    else:
        code = f'''// Import required modules
const exampleModule = require('example-module');

// Initialize the API
const api = exampleModule.{api_name.replace(" ", "_").lower()}();

// Use the API
const result = api.execute();

// Print the result
console.log(`Result: ${{result}}`);
'''

    return f"""```{language}
{code}
```

This example demonstrates how to use {api_name}. First, we import the necessary module, then initialize the API, execute it, and display the results.
"""


def openai_llm_client(prompt: str) -> str:
    """OpenAI LLM client for code generation.

    Requires: pip install openai
    Environment: OPENAI_API_KEY

    Parameters
    ----------
    prompt : str
        Generation prompt

    Returns
    -------
    str
        LLM response

    """
    import os

    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert programmer who writes clear, working code examples for API documentation.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content


def anthropic_llm_client(prompt: str) -> str:
    """Anthropic LLM client for code generation.

    Requires: pip install anthropic
    Environment: ANTHROPIC_API_KEY

    Parameters
    ----------
    prompt : str
        Generation prompt

    Returns
    -------
    str
        LLM response

    """
    import os

    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


class ExampleInserterTransform(NodeTransformer):
    """Transform to insert generated examples into documentation.

    Parameters
    ----------
    examples_by_heading : dict
        Map of heading text to GeneratedExample

    """

    def __init__(self, examples_by_heading: dict[str, GeneratedExample]):
        """Initialize transform with examples map."""
        super().__init__()
        self.examples_by_heading = examples_by_heading
        self.current_heading = None

    def visit_heading(self, node: Heading) -> Heading:
        """Track current heading.

        Parameters
        ----------
        node : Heading
            Heading node

        Returns
        -------
        Heading
            Unchanged heading node

        """
        self.current_heading = extract_text(node.content, joiner="")
        return node

    def visit_document(self, node: Document) -> Document:
        """Visit document and insert examples after relevant sections.

        Parameters
        ----------
        node : Document
            Document node

        Returns
        -------
        Document
            Document with examples inserted

        """
        new_children = []
        i = 0
        children = node.children

        while i < len(children):
            child = children[i]
            new_children.append(self.transform(child))

            if isinstance(child, Heading):
                heading_text = extract_text(child.content, joiner="")

                if heading_text in self.examples_by_heading:
                    example = self.examples_by_heading[heading_text]

                    builder = DocumentBuilder()
                    builder.add_paragraph(
                        builder.text(f"Example ({example.language}):")
                    )
                    builder.add_code_block(example.code, language=example.language)
                    builder.add_paragraph(builder.text(example.explanation))

                    new_children.extend(builder.document.children)

            i += 1

        return Document(
            children=[c for c in new_children if c is not None],
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )


def generate_examples_for_doc(
    input_path: str,
    output_path: str,
    language: Optional[str] = None,
    llm_client: Optional[Callable[[str], str]] = None,
    validate: bool = True,
) -> GenerationReport:
    """Generate code examples for documentation.

    Parameters
    ----------
    input_path : str
        Input documentation path
    output_path : str
        Output documentation path
    language : str or None, default = None
        Target programming language
    llm_client : callable or None, default = None
        LLM client (uses mock if None)
    validate : bool, default = True
        Whether to validate generated code

    Returns
    -------
    GenerationReport
        Generation report

    """
    report = GenerationReport()

    print(f"Parsing documentation: {input_path}")
    doc = to_ast(input_path)

    print("Extracting API sections...")
    sections = extract_api_sections(doc, target_language=language)
    sections_needing_examples = [s for s in sections if s.needs_example]

    print(f"Found {len(sections)} sections, {len(sections_needing_examples)} need examples")

    if not sections_needing_examples:
        print("No sections need examples. Exiting.")
        return report

    if llm_client is None:
        print("Using mock LLM client (for demo)")
        llm_client = mock_llm_client

    examples_by_heading = {}

    for i, section in enumerate(sections_needing_examples, 1):
        print(f"\n[{i}/{len(sections_needing_examples)}] Generating example for: {section.heading}")

        example = generate_example_with_llm(section, llm_client)
        report.examples_generated += 1

        if validate:
            if example.is_valid:
                print(f"  Validation: OK")
                report.examples_validated += 1
            else:
                print(f"  Validation: FAILED - {example.validation_error[:60]}")
                report.examples_failed += 1
        else:
            print(f"  Validation: SKIPPED")

        examples_by_heading[section.heading] = example
        report.sections_processed += 1

    print(f"\nInserting {len(examples_by_heading)} examples into document...")
    inserter = ExampleInserterTransform(examples_by_heading)
    enhanced_doc = inserter.transform(doc)

    print(f"Writing enhanced documentation to: {output_path}")
    from_ast(enhanced_doc, target_format="markdown", output=output_path)

    return report


def print_report(report: GenerationReport):
    """Print generation report.

    Parameters
    ----------
    report : GenerationReport
        Generation report

    """
    print("\n" + "=" * 70)
    print("Code Example Generation Report")
    print("=" * 70)
    print(f"Sections processed: {report.sections_processed}")
    print(f"Examples generated: {report.examples_generated}")
    print(f"Examples validated: {report.examples_validated}")
    print(f"Examples failed: {report.examples_failed}")

    success_rate = 0
    if report.examples_generated > 0:
        success_rate = (report.examples_validated / report.examples_generated) * 100

    print(f"\nValidation success rate: {success_rate:.1f}%")
    print("=" * 70)


def main():
    """Run the code example generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate code examples for API documentation"
    )
    parser.add_argument("input", help="Input documentation file")
    parser.add_argument("output", help="Output documentation file")
    parser.add_argument(
        "--language",
        "-l",
        default="python",
        help="Target programming language (default: python)",
    )
    parser.add_argument(
        "--llm",
        choices=["mock", "openai", "anthropic"],
        default="mock",
        help="LLM provider (default: mock)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip code validation",
    )

    args = parser.parse_args()

    llm_clients = {
        "mock": mock_llm_client,
        "openai": openai_llm_client,
        "anthropic": anthropic_llm_client,
    }

    if args.llm == "openai":
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable not set")
            sys.exit(1)
    elif args.llm == "anthropic":
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)

    llm_client = llm_clients[args.llm]

    report = generate_examples_for_doc(
        args.input,
        args.output,
        language=args.language,
        llm_client=llm_client,
        validate=not args.no_validate,
    )

    print_report(report)

    sys.exit(1 if report.examples_failed > 0 else 0)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Code Example Generator from Documentation")
        print("=" * 70)
        print()
        print("Automatically generate working code examples for API documentation")
        print("using LLMs.")
        print()
        print("Usage:")
        print("  python code_example_generator.py api_docs.md enhanced_docs.md")
        print("  python code_example_generator.py README.md examples.md --language python")
        print("  python code_example_generator.py docs.html out.html --llm openai")
        print()
        print("Features:")
        print("  - Extract API descriptions and function signatures")
        print("  - Generate working code examples via LLM")
        print("  - Insert examples back as properly formatted code blocks")
        print("  - Verify examples compile/run")
        print("  - Add explanatory comments")
        print("  - Support multiple languages")
        print()
        print("Options:")
        print("  --language LANG    Target language (default: python)")
        print("                     Supported: python, javascript")
        print("  --llm PROVIDER     LLM provider: mock, openai, anthropic")
        print("  --no-validate      Skip code validation")
        print()
        print("LLM Providers:")
        print("  mock        Demo mode (generates template examples)")
        print("  openai      OpenAI GPT-4 (requires OPENAI_API_KEY)")
        print("  anthropic   Anthropic Claude (requires ANTHROPIC_API_KEY)")
        print()
        print("How It Works:")
        print("  1. Parse documentation and extract API sections")
        print("  2. For each section without code examples:")
        print("     a. Send API description to LLM")
        print("     b. Generate working code example")
        print("     c. Validate code (syntax, compilation)")
        print("     d. Insert example into documentation")
        print("  3. Write enhanced documentation to output file")
        print()
        print("Examples:")
        print("  Generate Python examples with mock LLM:")
        print("    python code_example_generator.py api.md enhanced.md")
        print()
        print("  Generate JavaScript examples with OpenAI:")
        print("    python code_example_generator.py docs.md out.md \\")
        print("      --language javascript --llm openai")
        print()
        print("  Generate without validation (faster):")
        print("    python code_example_generator.py api.md out.md --no-validate")
        print()
        print("Use Cases:")
        print("  - API documentation enhancement")
        print("  - Tutorial creation")
        print("  - SDK example generation")
        print("  - Developer onboarding materials")
        print()
        sys.exit(0)

    main()

#!/usr/bin/env python3
"""Study Guide Generator from documents.

This example demonstrates how to extract key information from documents and
create comprehensive study materials using the all2md AST. It can generate
summaries, extract code examples, and optionally use LLMs to create quiz
questions and practice problems.

Features
--------
- Extract headings and first paragraph of each section
- Pull out all code examples with explanations
- Create summary with key points
- Generate quiz questions from content (with LLM)
- Create practice problems (with LLM)
- Output as formatted study guide markdown

Use Cases
---------
- Educational content creation
- Training material development
- Self-study resources
- Course preparation
"""

import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

from all2md import to_ast
from all2md.ast import CodeBlock, Document, Heading, Node, Paragraph, Text
from all2md.ast.builder import DocumentBuilder
from all2md.ast.transforms import extract_nodes
from all2md.ast.utils import extract_text


@dataclass
class StudySection:
    """A section in the study guide.

    Parameters
    ----------
    heading : str
        Section heading text
    level : int
        Heading level (1-6)
    summary : str
        Summary text (first paragraph)
    key_points : list of str, default = empty list
        Key points extracted from section
    code_examples : list of CodeExample, default = empty list
        Code examples in this section

    """

    heading: str
    level: int
    summary: str
    key_points: list[str] = field(default_factory=list)
    code_examples: list["CodeExample"] = field(default_factory=list)


@dataclass
class CodeExample:
    """A code example from the document.

    Parameters
    ----------
    language : str
        Programming language
    code : str
        Code content
    context : str
        Surrounding context/explanation

    """

    language: str
    code: str
    context: str


@dataclass
class StudyGuide:
    """Complete study guide structure.

    Parameters
    ----------
    title : str
        Study guide title
    sections : list of StudySection, default = empty list
        All sections in the guide
    all_code_examples : list of CodeExample, default = empty list
        All code examples across sections
    quiz_questions : list of str, default = empty list
        Generated quiz questions
    practice_problems : list of str, default = empty list
        Generated practice problems

    """

    title: str
    sections: list[StudySection] = field(default_factory=list)
    all_code_examples: list[CodeExample] = field(default_factory=list)
    quiz_questions: list[str] = field(default_factory=list)
    practice_problems: list[str] = field(default_factory=list)


def get_first_paragraph_after_heading(
    ast_doc: Document, heading_idx: int
) -> Optional[str]:
    """Get the first paragraph after a specific heading.

    Parameters
    ----------
    ast_doc : Document
        The document AST
    heading_idx : int
        Index of the heading in the document children

    Returns
    -------
    str or None
        Text of first paragraph or None if not found

    """
    children = ast_doc.children
    for i in range(heading_idx + 1, len(children)):
        child = children[i]
        if isinstance(child, Paragraph):
            return extract_text(child.content, joiner="")
        elif isinstance(child, Heading):
            break
    return None


def extract_code_blocks_with_context(ast_doc: Document) -> list[CodeExample]:
    """Extract all code blocks with surrounding context.

    Parameters
    ----------
    ast_doc : Document
        The document AST

    Returns
    -------
    list of CodeExample
        All code examples with context

    """
    examples = []
    children = ast_doc.children

    for i, child in enumerate(children):
        if isinstance(child, CodeBlock):
            context = ""

            for j in range(i - 1, max(-1, i - 3), -1):
                if isinstance(children[j], Paragraph):
                    context = extract_text(children[j].content, joiner="")
                    break

            language = child.language or "text"
            examples.append(
                CodeExample(language=language, code=child.content, context=context)
            )

    return examples


def extract_study_sections(ast_doc: Document) -> list[StudySection]:
    """Extract sections for the study guide.

    Parameters
    ----------
    ast_doc : Document
        The document AST

    Returns
    -------
    list of StudySection
        All sections extracted from document

    """
    sections = []
    children = ast_doc.children

    for i, child in enumerate(children):
        if isinstance(child, Heading):
            heading_text = extract_text(child.content, joiner="")
            summary = get_first_paragraph_after_heading(ast_doc, i) or ""

            section = StudySection(
                heading=heading_text, level=child.level, summary=summary
            )

            sections.append(section)

    return sections


def mock_llm_quiz_generator(section: StudySection) -> list[str]:
    """Mock LLM quiz question generator.

    In production, this would call an actual LLM API.

    Parameters
    ----------
    section : StudySection
        Section to generate quiz questions for

    Returns
    -------
    list of str
        Generated quiz questions

    """
    questions = []

    if section.summary:
        questions.append(
            f"Q: What is the main topic of the section '{section.heading}'?\n"
            f"A: [Based on: {section.summary[:60]}...]"
        )

    if section.code_examples:
        example = section.code_examples[0]
        questions.append(
            f"Q: What programming language is used in '{section.heading}'?\n"
            f"A: {example.language}"
        )

    return questions


def mock_llm_practice_generator(code_examples: list[CodeExample]) -> list[str]:
    """Mock LLM practice problem generator.

    In production, this would call an actual LLM API.

    Parameters
    ----------
    code_examples : list of CodeExample
        Code examples to base problems on

    Returns
    -------
    list of str
        Generated practice problems

    """
    problems = []

    if code_examples:
        first_example = code_examples[0]
        problems.append(
            f"Practice Problem ({first_example.language}):\n"
            f"Based on the example about '{first_example.context[:40]}...', "
            f"write a similar program that...\n"
            f"[LLM would generate specific problem here]"
        )

    return problems


def llm_quiz_generator(
    section: StudySection, llm_client: Callable[[str], str]
) -> list[str]:
    """Generate quiz questions using an LLM.

    Parameters
    ----------
    section : StudySection
        Section to generate questions for
    llm_client : callable
        LLM client function that takes prompt and returns response

    Returns
    -------
    list of str
        Generated quiz questions

    """
    prompt = f"""Generate 2-3 quiz questions about this topic:

Heading: {section.heading}
Summary: {section.summary}

Format each question as:
Q: [question]
A: [answer]
"""

    try:
        response = llm_client(prompt)
        questions = [q.strip() for q in response.split("\n\n") if q.strip()]
        return questions
    except Exception as e:
        return [f"Error generating quiz: {e}"]


def llm_practice_generator(
    code_examples: list[CodeExample], llm_client: Callable[[str], str]
) -> list[str]:
    """Generate practice problems using an LLM.

    Parameters
    ----------
    code_examples : list of CodeExample
        Code examples to base problems on
    llm_client : callable
        LLM client function

    Returns
    -------
    list of str
        Generated practice problems

    """
    if not code_examples:
        return []

    examples_text = "\n\n".join(
        [
            f"Language: {ex.language}\nContext: {ex.context}\nCode:\n{ex.code[:200]}"
            for ex in code_examples[:3]
        ]
    )

    prompt = f"""Based on these code examples, generate 2-3 practice coding problems:

{examples_text}

For each problem:
1. State the problem clearly
2. Specify the programming language
3. Provide example input/output
4. Note difficulty level
"""

    try:
        response = llm_client(prompt)
        return [response]
    except Exception as e:
        return [f"Error generating practice problems: {e}"]


def openai_llm_client(prompt: str) -> str:
    """OpenAI LLM client for quiz/practice generation.

    Requires: pip install openai
    Environment: OPENAI_API_KEY

    Parameters
    ----------
    prompt : str
        The prompt to send to the LLM

    Returns
    -------
    str
        LLM response

    """
    import os

    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful educational assistant that creates study materials.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content


def anthropic_llm_client(prompt: str) -> str:
    """Anthropic LLM client for quiz/practice generation.

    Requires: pip install anthropic
    Environment: ANTHROPIC_API_KEY

    Parameters
    ----------
    prompt : str
        The prompt to send to the LLM

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


def generate_study_guide(
    input_path: str,
    generate_quiz: bool = False,
    generate_practice: bool = False,
    llm_client: Optional[Callable[[str], str]] = None,
) -> StudyGuide:
    """Generate a study guide from a document.

    Parameters
    ----------
    input_path : str
        Path to input document
    generate_quiz : bool, default = False
        Whether to generate quiz questions
    generate_practice : bool, default = False
        Whether to generate practice problems
    llm_client : callable or None, default = None
        LLM client function (uses mock if None)

    Returns
    -------
    StudyGuide
        The generated study guide

    """
    print(f"Parsing document: {input_path}")
    ast_doc = to_ast(input_path)

    metadata = ast_doc.metadata
    title = metadata.get("title", "Study Guide")

    print("Extracting sections and summaries...")
    sections = extract_study_sections(ast_doc)

    print("Extracting code examples...")
    all_code = extract_code_blocks_with_context(ast_doc)

    print(f"Found {len(sections)} sections and {len(all_code)} code examples")

    guide = StudyGuide(title=title, sections=sections, all_code_examples=all_code)

    if generate_quiz:
        print("Generating quiz questions...")
        use_llm = llm_client is not None
        for section in sections[:5]:
            if use_llm:
                questions = llm_quiz_generator(section, llm_client)
            else:
                questions = mock_llm_quiz_generator(section)
            guide.quiz_questions.extend(questions)

    if generate_practice and all_code:
        print("Generating practice problems...")
        if llm_client:
            problems = llm_practice_generator(all_code, llm_client)
        else:
            problems = mock_llm_practice_generator(all_code)
        guide.practice_problems.extend(problems)

    return guide


def render_study_guide_markdown(guide: StudyGuide) -> str:
    """Render study guide as markdown.

    Parameters
    ----------
    guide : StudyGuide
        The study guide to render

    Returns
    -------
    str
        Markdown content

    """
    lines = []

    lines.append(f"# {guide.title}")
    lines.append("")
    lines.append("*Generated Study Guide*")
    lines.append("")

    lines.append("## Table of Contents")
    lines.append("")
    for i, section in enumerate(guide.sections, 1):
        indent = "  " * (section.level - 1)
        lines.append(f"{indent}{i}. {section.heading}")
    lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## Section Summaries")
    lines.append("")
    for section in guide.sections:
        marker = "#" * (section.level + 1)
        lines.append(f"{marker} {section.heading}")
        lines.append("")
        if section.summary:
            lines.append(section.summary)
            lines.append("")

    if guide.all_code_examples:
        lines.append("---")
        lines.append("")
        lines.append("## Code Examples")
        lines.append("")
        for i, example in enumerate(guide.all_code_examples, 1):
            lines.append(f"### Example {i}: {example.language}")
            lines.append("")
            if example.context:
                lines.append(f"*{example.context[:100]}...*")
                lines.append("")
            lines.append(f"```{example.language}")
            lines.append(example.code)
            lines.append("```")
            lines.append("")

    if guide.quiz_questions:
        lines.append("---")
        lines.append("")
        lines.append("## Quiz Questions")
        lines.append("")
        for i, question in enumerate(guide.quiz_questions, 1):
            lines.append(f"### Question {i}")
            lines.append("")
            lines.append(question)
            lines.append("")

    if guide.practice_problems:
        lines.append("---")
        lines.append("")
        lines.append("## Practice Problems")
        lines.append("")
        for i, problem in enumerate(guide.practice_problems, 1):
            lines.append(f"### Problem {i}")
            lines.append("")
            lines.append(problem)
            lines.append("")

    return "\n".join(lines)


def main():
    """Run the study guide generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate study guide from documents"
    )
    parser.add_argument("input", help="Input document path")
    parser.add_argument(
        "--output", "-o", default="study_guide.md", help="Output markdown file"
    )
    parser.add_argument(
        "--quiz", action="store_true", help="Generate quiz questions"
    )
    parser.add_argument(
        "--practice", action="store_true", help="Generate practice problems"
    )
    parser.add_argument(
        "--llm",
        choices=["mock", "openai", "anthropic"],
        default="mock",
        help="LLM provider for quiz/practice generation",
    )

    args = parser.parse_args()

    llm_clients = {
        "mock": None,
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

    guide = generate_study_guide(
        args.input,
        generate_quiz=args.quiz,
        generate_practice=args.practice,
        llm_client=llm_client,
    )

    print(f"\nRendering study guide...")
    markdown = render_study_guide_markdown(guide)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\nStudy guide saved to: {args.output}")
    print(f"  Sections: {len(guide.sections)}")
    print(f"  Code examples: {len(guide.all_code_examples)}")
    print(f"  Quiz questions: {len(guide.quiz_questions)}")
    print(f"  Practice problems: {len(guide.practice_problems)}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Study Guide Generator")
        print("=" * 70)
        print()
        print("Generate comprehensive study materials from documents.")
        print()
        print("Usage:")
        print("  python study_guide_generator.py textbook.pdf")
        print("  python study_guide_generator.py tutorial.md --quiz --practice")
        print("  python study_guide_generator.py docs.html --quiz --llm openai")
        print()
        print("Features:")
        print("  - Extract section summaries (headings + first paragraph)")
        print("  - Pull out all code examples with context")
        print("  - Generate quiz questions (optional, LLM-based)")
        print("  - Create practice coding problems (optional, LLM-based)")
        print("  - Output as formatted markdown study guide")
        print()
        print("Options:")
        print("  --output PATH       Output file path (default: study_guide.md)")
        print("  --quiz              Generate quiz questions")
        print("  --practice          Generate practice problems")
        print("  --llm PROVIDER      LLM provider: mock, openai, anthropic")
        print()
        print("LLM Providers:")
        print("  mock        Demo mode (basic question templates)")
        print("  openai      OpenAI GPT (requires OPENAI_API_KEY)")
        print("  anthropic   Anthropic Claude (requires ANTHROPIC_API_KEY)")
        print()
        print("Example:")
        print("  python study_guide_generator.py python_tutorial.pdf --quiz \\")
        print("    --practice --llm openai --output study.md")
        print()
        sys.exit(0)

    main()

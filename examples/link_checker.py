#!/usr/bin/env python3
"""Link Checker and Validator for documents.

This example demonstrates how to extract and validate all links in documents
using the all2md AST. It checks HTTP status codes, validates internal
references, and generates comprehensive reports with suggestions for fixes.

Features
--------
- Extract all links (internal and external) from any document format
- Check HTTP status of external links
- Validate internal document references (heading anchors)
- Report dead/broken links with location information
- Suggest fixes for common issues (http vs https, etc.)
- Generate link map/sitemap

Use Cases
---------
- Documentation maintenance
- Website migration validation
- SEO optimization
- Content quality assurance
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

from all2md import to_ast
from all2md.ast import Heading, Image, Link
from all2md.ast.transforms import extract_nodes
from all2md.ast.utils import extract_text


@dataclass
class LinkInfo:
    """Information about a link found in the document.

    Parameters
    ----------
    url : str
        The link URL
    text : str
        The link text or alt text
    link_type : str
        Type of link ('external', 'internal', 'anchor', 'image', 'email')
    source_location : str, default = ''
        Location in source document
    status_code : int or None, default = None
        HTTP status code (for external links)
    is_broken : bool, default = False
        Whether the link is broken
    error_message : str, default = ''
        Error message if link check failed
    suggested_fix : str, default = ''
        Suggested fix for broken links

    """

    url: str
    text: str
    link_type: str
    source_location: str = ""
    status_code: Optional[int] = None
    is_broken: bool = False
    error_message: str = ""
    suggested_fix: str = ""


@dataclass
class LinkCheckResult:
    """Results of link validation.

    Parameters
    ----------
    total_links : int, default = 0
        Total number of links found
    external_links : int, default = 0
        Number of external links
    internal_links : int, default = 0
        Number of internal links
    broken_links : int, default = 0
        Number of broken links
    warnings : int, default = 0
        Number of warnings
    links : list of LinkInfo, default = empty list
        Detailed information about all links

    """

    total_links: int = 0
    external_links: int = 0
    internal_links: int = 0
    broken_links: int = 0
    warnings: int = 0
    links: list[LinkInfo] = field(default_factory=list)


def classify_link(url: str) -> str:
    """Classify a link by type.

    Parameters
    ----------
    url : str
        The URL to classify

    Returns
    -------
    str
        Link type: 'external', 'internal', 'anchor', 'image', 'email', or 'unknown'

    """
    if not url:
        return "unknown"

    url_lower = url.lower()

    if url_lower.startswith("mailto:"):
        return "email"
    elif url_lower.startswith("#"):
        return "anchor"
    elif url_lower.startswith(("http://", "https://", "ftp://")):
        return "external"
    elif url_lower.startswith("data:"):
        return "image"
    elif url_lower.startswith(("/", "./")):
        return "internal"
    else:
        return "unknown"


def normalize_anchor(text: str) -> str:
    """Normalize text to create an anchor link.

    This follows GitHub-flavored markdown anchor generation rules.

    Parameters
    ----------
    text : str
        The heading text to normalize

    Returns
    -------
    str
        Normalized anchor

    """
    anchor = text.lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"[\s_]+", "-", anchor)
    anchor = anchor.strip("-")
    return anchor


def extract_all_links(ast_doc) -> list[LinkInfo]:
    """Extract all links and images from the document AST.

    Parameters
    ----------
    ast_doc : Document
        The document AST

    Returns
    -------
    list of LinkInfo
        All links found in the document

    """
    links = []

    link_nodes = extract_nodes(ast_doc, Link)
    for link_node in link_nodes:
        text = extract_text(link_node.content, joiner="")
        link_type = classify_link(link_node.url)

        source_info = ""
        if link_node.source_location:
            source_info = f"{link_node.source_location.format}"
            if link_node.source_location.page:
                source_info += f" page {link_node.source_location.page}"
            if link_node.source_location.line:
                source_info += f" line {link_node.source_location.line}"

        links.append(
            LinkInfo(
                url=link_node.url,
                text=text,
                link_type=link_type,
                source_location=source_info,
            )
        )

    image_nodes = extract_nodes(ast_doc, Image)
    for image_node in image_nodes:
        link_type = classify_link(image_node.url)

        source_info = ""
        if image_node.source_location:
            source_info = f"{image_node.source_location.format}"
            if image_node.source_location.page:
                source_info += f" page {image_node.source_location.page}"

        links.append(
            LinkInfo(
                url=image_node.url,
                text=image_node.alt_text,
                link_type="image",
                source_location=source_info,
            )
        )

    return links


def check_external_link(url: str, timeout: int = 10) -> tuple[Optional[int], str]:
    """Check the status of an external link.

    Parameters
    ----------
    url : str
        The URL to check
    timeout : int, default = 10
        Request timeout in seconds

    Returns
    -------
    tuple of (int or None, str)
        HTTP status code and error message if any

    """
    try:
        import httpx

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.head(url, timeout=timeout)
            if response.status_code == 405:
                response = client.get(url, timeout=timeout)
            return response.status_code, ""
    except ImportError:
        return None, "httpx not installed (pip install httpx)"
    except Exception as e:
        return None, str(e)


def validate_internal_anchor(anchor: str, headings: list[str]) -> bool:
    """Validate that an anchor link points to an existing heading.

    Parameters
    ----------
    anchor : str
        The anchor link (without the #)
    headings : list of str
        List of heading anchors in the document

    Returns
    -------
    bool
        True if anchor is valid

    """
    return anchor in headings


def suggest_fix(link_info: LinkInfo) -> str:
    """Suggest a fix for a broken link.

    Parameters
    ----------
    link_info : LinkInfo
        Information about the broken link

    Returns
    -------
    str
        Suggested fix or empty string if no suggestion

    """
    url = link_info.url

    if link_info.link_type == "external" and url.startswith("http://"):
        https_url = url.replace("http://", "https://", 1)
        return f"Try HTTPS: {https_url}"

    if link_info.status_code == 404:
        return "Link returns 404 - check if URL has moved or been deleted"

    if link_info.link_type == "anchor" and link_info.is_broken:
        return "Anchor not found - check heading text and capitalization"

    if "timeout" in link_info.error_message.lower():
        return "Request timeout - server may be slow or unreachable"

    return ""


def check_links(input_path: str, check_external: bool = True, timeout: int = 10) -> LinkCheckResult:
    """Check all links in a document.

    Parameters
    ----------
    input_path : str
        Path to document to check
    check_external : bool, default = True
        Whether to check external links (requires HTTP requests)
    timeout : int, default = 10
        Timeout for external link checks in seconds

    Returns
    -------
    LinkCheckResult
        Results of link validation

    """
    print(f"Parsing document: {input_path}")
    ast_doc = to_ast(input_path)

    print("Extracting links...")
    links = extract_all_links(ast_doc)

    print("Building heading index...")
    heading_nodes = extract_nodes(ast_doc, Heading)
    heading_anchors = [normalize_anchor(extract_text(h.content, joiner="")) for h in heading_nodes]

    result = LinkCheckResult(total_links=len(links))

    print(f"Found {len(links)} links. Validating...")

    for i, link_info in enumerate(links, 1):
        if link_info.link_type == "external":
            result.external_links += 1
            if check_external:
                print(f"  [{i}/{len(links)}] Checking {link_info.url[:60]}...")
                status_code, error = check_external_link(link_info.url, timeout)
                link_info.status_code = status_code

                if status_code and 200 <= status_code < 400:
                    pass
                else:
                    link_info.is_broken = True
                    link_info.error_message = error or f"HTTP {status_code}"
                    result.broken_links += 1
                    link_info.suggested_fix = suggest_fix(link_info)

        elif link_info.link_type == "anchor":
            result.internal_links += 1
            anchor = link_info.url.lstrip("#")
            if not validate_internal_anchor(anchor, heading_anchors):
                link_info.is_broken = True
                link_info.error_message = "Anchor target not found"
                result.broken_links += 1
                link_info.suggested_fix = suggest_fix(link_info)

        elif link_info.link_type in ("internal", "image"):
            result.internal_links += 1

        elif link_info.link_type == "email":
            pass

        else:
            result.warnings += 1
            link_info.error_message = f"Unknown link type: {link_info.link_type}"

    result.links = links
    return result


def print_report(result: LinkCheckResult, show_all: bool = False):
    """Print a formatted report of link checking results.

    Parameters
    ----------
    result : LinkCheckResult
        Results to report
    show_all : bool, default = False
        Show all links, not just broken ones

    """
    print("\n" + "=" * 70)
    print("Link Validation Report")
    print("=" * 70)
    print(f"Total links found: {result.total_links}")
    print(f"  External links: {result.external_links}")
    print(f"  Internal links: {result.internal_links}")
    print(f"  Broken links: {result.broken_links}")
    print(f"  Warnings: {result.warnings}")
    print("=" * 70)

    if result.broken_links > 0:
        print("\nBroken Links:")
        print("-" * 70)
        for link in result.links:
            if link.is_broken:
                print(f"\nURL: {link.url}")
                print(f"  Text: {link.text[:60]}")
                print(f"  Type: {link.link_type}")
                if link.source_location:
                    print(f"  Location: {link.source_location}")
                if link.status_code:
                    print(f"  Status: {link.status_code}")
                if link.error_message:
                    print(f"  Error: {link.error_message}")
                if link.suggested_fix:
                    print(f"  Suggestion: {link.suggested_fix}")

    if show_all:
        print("\nAll Links:")
        print("-" * 70)
        for link in result.links:
            status = "OK" if not link.is_broken else "BROKEN"
            print(f"{status:8} {link.link_type:10} {link.url[:50]}")

    print("\n" + "=" * 70)
    if result.broken_links == 0:
        print("All links are valid!")
    else:
        print(f"Found {result.broken_links} broken link(s).")
    print("=" * 70)


def generate_link_map(result: LinkCheckResult, output_path: str):
    """Generate a markdown link map file.

    Parameters
    ----------
    result : LinkCheckResult
        Link checking results
    output_path : str
        Path to write link map

    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Link Map\n\n")
        f.write(f"Total Links: {result.total_links}\n\n")

        f.write("## External Links\n\n")
        for link in result.links:
            if link.link_type == "external":
                status = "OK" if not link.is_broken else "BROKEN"
                f.write(f"- [{status}] [{link.text}]({link.url})\n")

        f.write("\n## Internal Links\n\n")
        for link in result.links:
            if link.link_type in ("internal", "anchor"):
                status = "OK" if not link.is_broken else "BROKEN"
                f.write(f"- [{status}] [{link.text}]({link.url})\n")

        f.write("\n## Images\n\n")
        for link in result.links:
            if link.link_type == "image":
                f.write(f"- ![{link.text}]({link.url[:60]})\n")

    print(f"\nLink map saved to: {output_path}")


def main():
    """Run the link checker."""
    import argparse

    parser = argparse.ArgumentParser(description="Check and validate all links in a document")
    parser.add_argument("input", help="Input document path")
    parser.add_argument(
        "--no-external",
        action="store_true",
        help="Skip checking external links (faster)",
    )
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for external checks (seconds)")
    parser.add_argument("--show-all", action="store_true", help="Show all links, not just broken ones")
    parser.add_argument("--link-map", type=str, help="Generate link map file at specified path")

    args = parser.parse_args()

    result = check_links(args.input, check_external=not args.no_external, timeout=args.timeout)

    print_report(result, show_all=args.show_all)

    if args.link_map:
        generate_link_map(result, args.link_map)

    sys.exit(1 if result.broken_links > 0 else 0)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Link Checker and Validator")
        print("=" * 70)
        print()
        print("Extract and validate all links in documents.")
        print()
        print("Usage:")
        print("  python link_checker.py document.pdf")
        print("  python link_checker.py README.md --show-all")
        print("  python link_checker.py docs.html --no-external")
        print("  python link_checker.py guide.docx --link-map links.md")
        print()
        print("Features:")
        print("  - Extract all links (external, internal, anchors, images)")
        print("  - Check HTTP status of external links")
        print("  - Validate internal heading anchors")
        print("  - Report broken links with suggestions")
        print("  - Generate link map/sitemap")
        print()
        print("Options:")
        print("  --no-external    Skip external link checking (faster)")
        print("  --timeout N      Set timeout for external checks (default: 10s)")
        print("  --show-all       Show all links, not just broken ones")
        print("  --link-map PATH  Generate link map markdown file")
        print()
        print("Requires: httpx (pip install httpx)")
        print()
        sys.exit(0)

    main()

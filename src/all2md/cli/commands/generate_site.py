#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""Static site generation command for all2md CLI.

This module provides the generate-site command for converting documents
to Hugo or Jekyll static site formats. It handles frontmatter generation,
asset copying, and site scaffolding to create ready-to-deploy static sites
from various document formats.
"""
import argparse
import logging
import sys
from pathlib import Path

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS, EXIT_VALIDATION_ERROR
from all2md.cli.commands.shared import collect_input_files
from all2md.renderers.markdown import MarkdownRenderer
from all2md.utils.attachments import ensure_unique_attachment_path
from all2md.utils.static_site import (
    FrontmatterFormat,
    FrontmatterGenerator,
    SiteScaffolder,
    StaticSiteGenerator,
    copy_document_assets,
    generate_output_filename,
)

logger = logging.getLogger(__name__)


def handle_generate_site_command(args: list[str] | None = None) -> int:
    """Handle generate-site command for Hugo/Jekyll static site generation.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'generate-site')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    parser = argparse.ArgumentParser(
        prog="all2md generate-site",
        description="Generate Hugo or Jekyll static site from documents.",
    )
    parser.add_argument("input", nargs="+", help="Input files or directories to convert")
    parser.add_argument("--output-dir", required=True, help="Output directory for the static site")
    parser.add_argument(
        "--generator", choices=["hugo", "jekyll"], required=True, help="Static site generator (hugo or jekyll)"
    )
    parser.add_argument(
        "--scaffold", action="store_true", help="Create full site structure with config files and layouts"
    )
    parser.add_argument(
        "--frontmatter-format",
        choices=["yaml", "toml"],
        help="Frontmatter format (default: toml for Hugo, yaml for Jekyll)",
    )
    parser.add_argument(
        "--content-subdir", default="", help="Subdirectory within content/ or _posts/ (e.g., 'posts', 'docs')"
    )
    parser.add_argument("--recursive", action="store_true", help="Process directories recursively")
    parser.add_argument("--exclude", action="append", help="Glob patterns to exclude (can be used multiple times)")

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    # Parse generator type
    generator = StaticSiteGenerator(parsed.generator)

    # Determine frontmatter format
    if parsed.frontmatter_format:
        fm_format = FrontmatterFormat(parsed.frontmatter_format)
    else:
        fm_format = FrontmatterFormat.TOML if generator == StaticSiteGenerator.HUGO else FrontmatterFormat.YAML

    # Create output directory
    output_dir = Path(parsed.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold site structure if requested
    if parsed.scaffold:
        scaffolder = SiteScaffolder(generator)
        scaffolder.scaffold(output_dir)
        print(f"Created {generator.value} site structure at {output_dir}")

    # Collect input files
    items = collect_input_files(parsed.input, parsed.recursive, exclude_patterns=parsed.exclude)

    if not items:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Determine content directory
    if generator == StaticSiteGenerator.HUGO:
        content_dir = output_dir / "content"
        if parsed.content_subdir:
            content_dir = content_dir / parsed.content_subdir
    else:  # Jekyll
        content_dir = output_dir / "_posts"
        if parsed.content_subdir:
            content_dir = output_dir / parsed.content_subdir

    content_dir.mkdir(parents=True, exist_ok=True)

    # Process each file
    frontmatter_gen = FrontmatterGenerator(generator, fm_format)
    markdown_renderer = MarkdownRenderer()
    success_count = 0
    error_count = 0

    print(f"Converting {len(items)} file(s) to {generator.value} site...")
    from all2md.api import to_ast

    for index, item in enumerate(items, start=1):
        try:
            # Get source path
            source_path = item.best_path()
            if not source_path:
                logger.warning(f"Skipping item with no path: {item.display_name}")
                continue

            # Convert to AST
            logger.debug(f"Processing {source_path}")
            doc = to_ast(source_path)

            # Generate frontmatter from metadata
            frontmatter = frontmatter_gen.generate(doc.metadata)

            # Copy assets and update image URLs
            doc, copied_assets = copy_document_assets(doc, output_dir, generator, source_path)
            if copied_assets:
                logger.debug(f"Copied {len(copied_assets)} asset(s) for {source_path.name}")

            # Render markdown content
            markdown_content = markdown_renderer.render_to_string(doc)

            # Combine frontmatter and content
            full_content = frontmatter + markdown_content

            # Generate output filename
            output_filename = generate_output_filename(source_path, doc.metadata, generator, index)
            output_path = content_dir / f"{output_filename}.md"

            # Ensure unique filename
            output_path = ensure_unique_attachment_path(output_path)

            # Write output file
            output_path.write_text(full_content, encoding="utf-8")
            print(f"  [{index}/{len(items)}] {source_path.name} -> {output_path.relative_to(output_dir)}")
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to process {item.display_name}: {e}")
            print(f"  [ERROR] {item.display_name}: {e}", file=sys.stderr)
            error_count += 1
            continue

    # Summary
    print(f"\nCompleted: {success_count} successful, {error_count} errors")
    print(f"Site created at: {output_dir}")

    if generator == StaticSiteGenerator.HUGO:
        print("\nTo preview your Hugo site:")
        print(f"  cd {output_dir}")
        print("  hugo server")
    else:
        print("\nTo preview your Jekyll site:")
        print(f"  cd {output_dir}")
        print("  jekyll serve")

    return EXIT_SUCCESS if error_count == 0 else EXIT_ERROR

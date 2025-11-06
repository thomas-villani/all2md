#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/static_site.py
"""Static site generator utilities for Hugo and Jekyll.

This module provides utilities for converting documents to static site
generator formats (Hugo, Jekyll). It handles:
- Frontmatter generation from document metadata
- Site structure scaffolding
- Asset management for static sites

Functions
---------
- generate_frontmatter: Convert Document metadata to frontmatter
- create_site_scaffold: Create Hugo/Jekyll site directory structure
- process_document_for_static_site: Convert document with frontmatter and assets
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tomli_w
import yaml

from all2md.ast.nodes import Document, Image, Node
from all2md.utils.attachments import ensure_unique_attachment_path, sanitize_attachment_filename
from all2md.utils.text import slugify

logger = logging.getLogger(__name__)


class StaticSiteGenerator(str, Enum):
    """Supported static site generators."""

    HUGO = "hugo"
    JEKYLL = "jekyll"


class FrontmatterFormat(str, Enum):
    """Frontmatter serialization formats."""

    YAML = "yaml"
    TOML = "toml"


class FrontmatterGenerator:
    """Generate frontmatter for static site generators.

    This class handles conversion of Document metadata to generator-specific
    frontmatter in YAML or TOML format.

    Parameters
    ----------
    generator : StaticSiteGenerator
        Target static site generator
    format : FrontmatterFormat, optional
        Frontmatter format (defaults based on generator)

    Examples
    --------
    Generate Hugo frontmatter:

        >>> generator = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        >>> metadata = {"title": "My Post", "date": "2025-01-22", "tags": ["python", "coding"]}
        >>> frontmatter = generator.generate(metadata)

    """

    def __init__(
        self,
        generator: StaticSiteGenerator,
        format: Optional[FrontmatterFormat] = None,
    ):
        """Initialize frontmatter generator.

        Parameters
        ----------
        generator : StaticSiteGenerator
            Target static site generator
        format : FrontmatterFormat, optional
            Frontmatter format. If None, uses TOML for Hugo and YAML for Jekyll.

        """
        self.generator = generator
        self.format = format or self._get_default_format(generator)

    @staticmethod
    def _get_default_format(generator: StaticSiteGenerator) -> FrontmatterFormat:
        """Get default frontmatter format for a generator.

        Parameters
        ----------
        generator : StaticSiteGenerator
            Target generator

        Returns
        -------
        FrontmatterFormat
            Default format for the generator

        """
        if generator == StaticSiteGenerator.HUGO:
            return FrontmatterFormat.TOML
        return FrontmatterFormat.YAML

    def generate(self, metadata: Dict[str, Any]) -> str:
        """Generate frontmatter from document metadata.

        Parameters
        ----------
        metadata : dict
            Document metadata dictionary

        Returns
        -------
        str
            Formatted frontmatter with delimiters

        Examples
        --------
        >>> generator = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        >>> metadata = {"title": "Test", "date": "2025-01-22"}
        >>> print(generator.generate(metadata))
        +++
        title = "Test"
        date = 2025-01-22
        +++

        """
        # Normalize metadata to generator-specific fields
        normalized = self._normalize_metadata(metadata)

        # Serialize to format using library helpers
        if self.format == FrontmatterFormat.TOML:
            content = tomli_w.dumps(normalized)
            if not content.endswith("\n"):
                content += "\n"
            return f"+++\n{content}+++\n\n"

        content = yaml.safe_dump(
            normalized,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
        if not content.endswith("\n"):
            content += "\n"
        return f"---\n{content}---\n\n"

    def _normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize metadata to generator-specific fields.

        Parameters
        ----------
        metadata : dict
            Raw document metadata

        Returns
        -------
        dict
            Normalized metadata for the target generator

        """
        normalized = {}

        # Common fields across generators
        if "title" in metadata:
            normalized["title"] = metadata["title"]

        # Handle dates - prefer creation_date, fall back to date
        date_value = metadata.get("creation_date") or metadata.get("date")
        if date_value:
            normalized["date"] = self._format_date(date_value)

        # Handle author
        if "author" in metadata:
            normalized["author"] = metadata["author"]

        # Handle description/subject
        if "description" in metadata:
            normalized["description"] = metadata["description"]
        elif "subject" in metadata:
            normalized["description"] = metadata["subject"]

        # Handle tags and categories (taxonomy mapping)
        tags = self._extract_taxonomy(metadata, "tags", "keywords")
        if tags:
            normalized["tags"] = tags

        categories = self._extract_taxonomy(metadata, "categories", "category")
        if categories:
            normalized["categories"] = categories

        # Generator-specific fields
        if self.generator == StaticSiteGenerator.HUGO:
            normalized["draft"] = metadata.get("draft", False)
            if "weight" in metadata:
                normalized["weight"] = metadata["weight"]
        elif self.generator == StaticSiteGenerator.JEKYLL:
            if "layout" in metadata:
                normalized["layout"] = metadata["layout"]
            else:
                normalized["layout"] = "post"  # Default Jekyll layout
            if "permalink" in metadata:
                normalized["permalink"] = metadata["permalink"]

        return normalized

    def _extract_taxonomy(self, metadata: Dict[str, Any], primary_key: str, fallback_key: str) -> Optional[List[str]]:
        """Extract taxonomy terms from metadata.

        Parameters
        ----------
        metadata : dict
            Document metadata
        primary_key : str
            Primary key to check (e.g., "tags")
        fallback_key : str
            Fallback key to check (e.g., "keywords")

        Returns
        -------
        list of str or None
            List of taxonomy terms or None if not found

        """
        value = metadata.get(primary_key) or metadata.get(fallback_key)
        if not value:
            return None

        # Handle string (comma-separated) or list
        if isinstance(value, str):
            # Split on commas and clean whitespace
            terms = [term.strip() for term in value.split(",")]
            return [t for t in terms if t]
        elif isinstance(value, list):
            return value
        return None

    @staticmethod
    def _format_date(date_value: Any) -> str:
        """Format date value for frontmatter.

        Parameters
        ----------
        date_value : Any
            Date value (datetime, str, etc.)

        Returns
        -------
        str
            ISO-formatted date string

        """
        if isinstance(date_value, datetime):
            return date_value.isoformat()
        elif isinstance(date_value, str):
            # Try to parse and reformat
            try:
                dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
                return dt.isoformat()
            except ValueError:
                # Return as-is if parsing fails
                return date_value
        return str(date_value)


class SiteScaffolder:
    """Create directory structure for static site generators.

    This class handles creation of the basic directory structure and
    configuration files for Hugo and Jekyll sites.

    Parameters
    ----------
    generator : StaticSiteGenerator
        Target static site generator

    """

    def __init__(self, generator: StaticSiteGenerator):
        """Initialize site scaffolder.

        Parameters
        ----------
        generator : StaticSiteGenerator
            Target generator

        """
        self.generator = generator

    def scaffold(self, output_dir: Path) -> None:
        """Create site directory structure.

        Parameters
        ----------
        output_dir : Path
            Root directory for the site

        """
        if self.generator == StaticSiteGenerator.HUGO:
            self._scaffold_hugo(output_dir)
        elif self.generator == StaticSiteGenerator.JEKYLL:
            self._scaffold_jekyll(output_dir)

    def _scaffold_hugo(self, output_dir: Path) -> None:
        """Create Hugo site structure.

        Parameters
        ----------
        output_dir : Path
            Root directory for the Hugo site

        """
        # Create directory structure
        (output_dir / "content").mkdir(parents=True, exist_ok=True)
        (output_dir / "static" / "images").mkdir(parents=True, exist_ok=True)
        (output_dir / "themes").mkdir(parents=True, exist_ok=True)
        (output_dir / "layouts").mkdir(parents=True, exist_ok=True)
        (output_dir / "data").mkdir(parents=True, exist_ok=True)

        # Create config.toml
        config_content = self._get_hugo_config()
        (output_dir / "config.toml").write_text(config_content, encoding="utf-8")

        # Create content index
        index_content = """+++
title = "Home"
+++

# Welcome

This site was generated using all2md.
"""
        (output_dir / "content" / "_index.md").write_text(index_content, encoding="utf-8")

        # Create themes README
        themes_readme = """# Themes

Add Hugo themes to this directory.

To install a theme:
```bash
cd themes
git clone https://github.com/theNewDynamic/gohugo-theme-ananke.git
```

Then update config.toml:
```toml
theme = "gohugo-theme-ananke"
```
"""
        (output_dir / "themes" / "README.md").write_text(themes_readme, encoding="utf-8")

        logger.info(f"Created Hugo site structure at {output_dir}")

    def _scaffold_jekyll(self, output_dir: Path) -> None:
        """Create Jekyll site structure.

        Parameters
        ----------
        output_dir : Path
            Root directory for the Jekyll site

        """
        # Create directory structure
        (output_dir / "_posts").mkdir(parents=True, exist_ok=True)
        (output_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
        (output_dir / "_layouts").mkdir(parents=True, exist_ok=True)
        (output_dir / "_includes").mkdir(parents=True, exist_ok=True)

        # Create _config.yml
        config_content = self._get_jekyll_config()
        (output_dir / "_config.yml").write_text(config_content, encoding="utf-8")

        # Create index.md
        index_content = """---
layout: default
title: Home
---

# Welcome

This site was generated using all2md.
"""
        (output_dir / "index.md").write_text(index_content, encoding="utf-8")

        # Create default layout
        layout_content = self._get_jekyll_default_layout()
        (output_dir / "_layouts" / "default.html").write_text(layout_content, encoding="utf-8")

        # Create post layout
        post_layout = self._get_jekyll_post_layout()
        (output_dir / "_layouts" / "post.html").write_text(post_layout, encoding="utf-8")

        logger.info(f"Created Jekyll site structure at {output_dir}")

    @staticmethod
    def _get_hugo_config() -> str:
        """Get Hugo configuration template.

        Returns
        -------
        str
            Hugo config.toml content

        """
        return """baseURL = "http://example.org/"
languageCode = "en-us"
title = "My Site"

[params]
  description = "Site generated with all2md"

[markup]
  [markup.goldmark]
    [markup.goldmark.renderer]
      unsafe = true
"""

    @staticmethod
    def _get_jekyll_config() -> str:
        """Get Jekyll configuration template.

        Returns
        -------
        str
            Jekyll _config.yml content

        """
        return """title: My Site
description: Site generated with all2md
baseurl: ""
url: "http://example.org"

# Build settings
markdown: kramdown
theme: minima

# Collections
collections:
  posts:
    output: true
    permalink: /:year/:month/:day/:title/

# Defaults
defaults:
  - scope:
      path: ""
      type: "posts"
    values:
      layout: "post"
"""

    @staticmethod
    def _get_jekyll_default_layout() -> str:
        """Get Jekyll default layout template.

        Returns
        -------
        str
            Jekyll default.html content

        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page.title }} - {{ site.title }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3 { color: #333; }
        pre { background: #f4f4f4; padding: 10px; overflow-x: auto; }
        code { background: #f4f4f4; padding: 2px 6px; }
    </style>
</head>
<body>
    <header>
        <h1><a href="{{ site.baseurl }}/">{{ site.title }}</a></h1>
        <p>{{ site.description }}</p>
    </header>

    <main>
        {{ content }}
    </main>

    <footer>
        <p>&copy; {{ site.time | date: '%Y' }} {{ site.title }}</p>
    </footer>
</body>
</html>
"""

    @staticmethod
    def _get_jekyll_post_layout() -> str:
        """Get Jekyll post layout template.

        Returns
        -------
        str
            Jekyll post.html content

        """
        return """---
layout: default
---

<article>
    <header>
        <h1>{{ page.title }}</h1>
        <p class="meta">
            {{ page.date | date: "%B %d, %Y" }}
            {% if page.author %} by {{ page.author }}{% endif %}
        </p>
    </header>

    {{ content }}

    {% if page.tags %}
    <footer>
        <p>Tags: {{ page.tags | join: ", " }}</p>
    </footer>
    {% endif %}
</article>
"""


class ImageCollector:
    """Utility to collect all Image nodes from a document AST.

    This class walks the document AST and collects all Image nodes.

    Attributes
    ----------
    images : list
        List of Image nodes found in the document

    """

    def __init__(self) -> None:
        """Initialize the image collector."""
        self.images: List[Image] = []

    def collect(self, node: Node) -> None:
        """Collect images from a node and its children.

        Parameters
        ----------
        node : Node
            Node to collect images from

        """
        # If this is an Image node, collect it
        if isinstance(node, Image):
            self.images.append(node)
            return

        # Recursively visit children
        if hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                self.collect(child)

        # Recursively visit inline content
        if hasattr(node, "content") and isinstance(node.content, list):
            for child in node.content:
                self.collect(child)


def copy_document_assets(
    doc: Document,
    output_dir: Path,
    generator: StaticSiteGenerator,
    source_file: Optional[Path] = None,
) -> Tuple[Document, List[str]]:
    """Copy document assets to static site directory and update references.

    This function walks the document AST, finds all images with file paths,
    copies them to the appropriate static directory, and updates the image
    URLs in the AST to reference the new locations.

    Parameters
    ----------
    doc : Document
        Document AST with image nodes
    output_dir : Path
        Root output directory for the static site
    generator : StaticSiteGenerator
        Target static site generator (Hugo or Jekyll)
    source_file : Path, optional
        Source file path (used to resolve relative image paths)

    Returns
    -------
    tuple[Document, list of str]
        Tuple of (modified_document, list_of_copied_assets)
        The document is modified in-place, but returned for convenience.

    Examples
    --------
    Copy assets from a document:

        >>> from all2md import to_ast
        >>> doc = to_ast("document.pdf")
        >>> modified_doc, assets = copy_document_assets(
        ...     doc, Path("./my-site"), StaticSiteGenerator.HUGO
        ... )
        >>> print(f"Copied {len(assets)} assets")

    """
    # Determine static directory based on generator
    if generator == StaticSiteGenerator.HUGO:
        static_dir = output_dir / "static" / "images"
    else:  # Jekyll
        static_dir = output_dir / "assets" / "images"

    # Ensure static directory exists
    static_dir.mkdir(parents=True, exist_ok=True)

    # Collect all images from the document
    collector = ImageCollector()
    collector.collect(doc)

    copied_assets: List[str] = []

    for image in collector.images:
        # Skip data URIs and remote URLs
        if image.url.startswith(("data:", "http:", "https:")):
            continue

        # Resolve image path
        image_path = Path(image.url)

        # If relative path and we have source file, resolve relative to source
        if not image_path.is_absolute() and source_file:
            image_path = source_file.parent / image_path

        # Check if image file exists
        if not image_path.exists():
            logger.warning(f"Image file not found: {image_path}")
            continue

        try:
            # Sanitize filename for safe storage
            safe_filename = sanitize_attachment_filename(image_path.name, preserve_case=True, allow_unicode=False)

            # Determine destination path
            dest_path = static_dir / safe_filename

            # Handle collisions by ensuring unique path
            dest_path = ensure_unique_attachment_path(dest_path)

            # Copy the image file
            shutil.copy2(image_path, dest_path)
            logger.debug(f"Copied asset: {image_path} -> {dest_path}")

            # Update image URL in AST to reference static location
            # Use relative path from content directory
            if generator == StaticSiteGenerator.HUGO:
                # Hugo uses /static/ prefix
                image.url = f"/images/{dest_path.name}"
            else:  # Jekyll
                # Jekyll uses /assets/ prefix
                image.url = f"/assets/images/{dest_path.name}"

            copied_assets.append(str(dest_path))

        except Exception as e:
            logger.error(f"Failed to copy asset {image_path}: {e}")
            continue

    return doc, copied_assets


def generate_output_filename(
    source_file: Path,
    metadata: Dict[str, Any],
    generator: StaticSiteGenerator,
    index: int = 1,
) -> str:
    """Generate output filename for a document.

    Creates a filename based on the document title (if available),
    source filename, or index. For Jekyll posts, prepends the date
    in YYYY-MM-DD format.

    Parameters
    ----------
    source_file : Path
        Source document path
    metadata : dict
        Document metadata (may contain title, date)
    generator : StaticSiteGenerator
        Target generator
    index : int, default 1
        Numeric index for fallback naming

    Returns
    -------
    str
        Generated output filename (without extension)

    Examples
    --------
    Generate Hugo filename:

        >>> from pathlib import Path
        >>> metadata = {"title": "My Great Post"}
        >>> generate_output_filename(
        ...     Path("doc.pdf"), metadata, StaticSiteGenerator.HUGO
        ... )
        'my-great-post'

    Generate Jekyll filename with date:

        >>> metadata = {"title": "My Post", "date": "2025-01-22"}
        >>> generate_output_filename(
        ...     Path("doc.pdf"), metadata, StaticSiteGenerator.JEKYLL
        ... )
        '2025-01-22-my-post'

    """
    # Try to get title from metadata
    title = metadata.get("title", "")

    if title:
        # Use slugified title
        base_name = slugify(title)
    else:
        # Fall back to source file stem
        base_name = slugify(source_file.stem)

    # If still empty, use index
    if not base_name or base_name == "section":
        base_name = f"document-{index}"

    # For Jekyll, prepend date if available (posts require YYYY-MM-DD prefix)
    if generator == StaticSiteGenerator.JEKYLL:
        date_str = metadata.get("creation_date") or metadata.get("date")
        if date_str:
            # Parse date and format as YYYY-MM-DD
            try:
                if isinstance(date_str, datetime):
                    date_prefix = date_str.strftime("%Y-%m-%d")
                else:
                    # Try parsing ISO format
                    dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    date_prefix = dt.strftime("%Y-%m-%d")
                base_name = f"{date_prefix}-{base_name}"
            except (ValueError, AttributeError):
                logger.warning(f"Could not parse date: {date_str}")

    return base_name

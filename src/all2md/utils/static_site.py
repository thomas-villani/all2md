#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/static_site.py
"""Static site generator utilities for Hugo, Jekyll, MkDocs, Zola, and Eleventy.

This module provides utilities for converting documents to static site
generator formats (Hugo, Jekyll, MkDocs, Zola, Eleventy). It handles:
- Frontmatter generation from document metadata
- Site structure scaffolding
- Asset management for static sites

Functions
---------
- generate_frontmatter: Convert Document metadata to frontmatter
- create_site_scaffold: Create static site directory structure
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
    MKDOCS = "mkdocs"
    ZOLA = "zola"
    ELEVENTY = "eleventy"


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
            Frontmatter format. If None, uses TOML for Hugo and Zola, and
            YAML for Jekyll, MkDocs, and Eleventy.

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
        # Hugo and Zola both default to TOML (+++); the rest default to YAML (---).
        if generator in (StaticSiteGenerator.HUGO, StaticSiteGenerator.ZOLA):
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
        elif self.generator == StaticSiteGenerator.ZOLA:
            # Zola validates front matter against a fixed schema and errors on
            # unknown top-level keys: tags/categories must live under
            # [taxonomies] and non-standard fields (author) under [extra].
            taxonomies: Dict[str, Any] = {}
            if "tags" in normalized:
                taxonomies["tags"] = normalized.pop("tags")
            if "categories" in normalized:
                taxonomies["categories"] = normalized.pop("categories")
            extra: Dict[str, Any] = {}
            if "author" in normalized:
                extra["author"] = normalized.pop("author")
            normalized["draft"] = metadata.get("draft", False)
            if "weight" in metadata:
                normalized["weight"] = metadata["weight"]
            if taxonomies:
                normalized["taxonomies"] = taxonomies
            if extra:
                normalized["extra"] = extra
        # Eleventy and MkDocs use the common fields as-is (no schema constraints).

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
    configuration files for Hugo, Jekyll, MkDocs, Zola, and Eleventy sites.

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
        elif self.generator == StaticSiteGenerator.MKDOCS:
            self._scaffold_mkdocs(output_dir)
        elif self.generator == StaticSiteGenerator.ZOLA:
            self._scaffold_zola(output_dir)
        elif self.generator == StaticSiteGenerator.ELEVENTY:
            self._scaffold_eleventy(output_dir)

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

    def _scaffold_mkdocs(self, output_dir: Path) -> None:
        """Create MkDocs site structure.

        Parameters
        ----------
        output_dir : Path
            Root directory for the MkDocs site

        """
        # Create directory structure. MkDocs keeps all content (and assets)
        # under the docs/ directory; mkdocs.yml lives at the project root.
        (output_dir / "docs" / "images").mkdir(parents=True, exist_ok=True)

        # Create mkdocs.yml
        config_content = self._get_mkdocs_config()
        (output_dir / "mkdocs.yml").write_text(config_content, encoding="utf-8")

        # Create homepage (MkDocs uses docs/index.md as the site root)
        index_content = """# Welcome

This site was generated using all2md.
"""
        (output_dir / "docs" / "index.md").write_text(index_content, encoding="utf-8")

        logger.info(f"Created MkDocs site structure at {output_dir}")

    def _scaffold_zola(self, output_dir: Path) -> None:
        """Create Zola site structure.

        Parameters
        ----------
        output_dir : Path
            Root directory for the Zola site

        """
        # Create directory structure. Zola uses content/ for pages, static/
        # for assets (served at the site root), and templates/ for Tera templates.
        (output_dir / "content").mkdir(parents=True, exist_ok=True)
        (output_dir / "static" / "images").mkdir(parents=True, exist_ok=True)
        (output_dir / "templates").mkdir(parents=True, exist_ok=True)

        # Create config.toml
        (output_dir / "config.toml").write_text(self._get_zola_config(), encoding="utf-8")

        # Create section index (Zola renders content/_index.md via templates/index.html)
        index_content = """+++
title = "Home"
+++

# Welcome

This site was generated using all2md.
"""
        (output_dir / "content" / "_index.md").write_text(index_content, encoding="utf-8")

        # Create minimal Tera templates so `zola build` works out of the box
        templates = {
            "base.html": self._get_zola_base_template(),
            "index.html": self._get_zola_index_template(),
            "section.html": self._get_zola_index_template(),
            "page.html": self._get_zola_page_template(),
        }
        for name, content in templates.items():
            (output_dir / "templates" / name).write_text(content, encoding="utf-8")

        logger.info(f"Created Zola site structure at {output_dir}")

    def _scaffold_eleventy(self, output_dir: Path) -> None:
        """Create Eleventy (11ty) site structure.

        Parameters
        ----------
        output_dir : Path
            Root directory for the Eleventy site

        """
        # Create directory structure. Eleventy reads content from the input
        # directory (src/) and passes src/images/ straight through to the output.
        (output_dir / "src" / "images").mkdir(parents=True, exist_ok=True)

        # Create config and package.json
        (output_dir / ".eleventy.js").write_text(self._get_eleventy_config(), encoding="utf-8")
        (output_dir / "package.json").write_text(self._get_eleventy_package_json(), encoding="utf-8")

        # Create homepage
        index_content = """---
title: Home
---

# Welcome

This site was generated using all2md.
"""
        (output_dir / "src" / "index.md").write_text(index_content, encoding="utf-8")

        logger.info(f"Created Eleventy site structure at {output_dir}")

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
    def _get_mkdocs_config() -> str:
        """Get MkDocs configuration template.

        Returns
        -------
        str
            MkDocs mkdocs.yml content

        """
        return """site_name: My Site
site_description: Site generated with all2md

# The Material theme is recommended (pip install mkdocs-material).
# Switch to the built-in "readthedocs" or "mkdocs" theme to avoid the extra dependency.
theme:
  name: material

markdown_extensions:
  - admonition
  - tables
  - fenced_code
  - toc:
      permalink: true
"""

    @staticmethod
    def _get_zola_config() -> str:
        """Get Zola configuration template.

        Returns
        -------
        str
            Zola config.toml content

        """
        return """base_url = "https://example.org"
title = "My Site"
description = "Site generated with all2md"

compile_sass = false
build_search_index = false

[markdown]
highlight_code = true

[taxonomies]
tags = []
categories = []

[extra]
"""

    @staticmethod
    def _get_zola_base_template() -> str:
        """Get the base Tera template for a scaffolded Zola site."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ config.title }}{% endblock title %}</title>
</head>
<body>
    <header>
        <h1><a href="{{ config.base_url }}">{{ config.title }}</a></h1>
    </header>
    <main>
        {% block content %}{% endblock content %}
    </main>
</body>
</html>
"""

    @staticmethod
    def _get_zola_index_template() -> str:
        """Get the section (index) Tera template for a scaffolded Zola site."""
        return """{% extends "base.html" %}
{% block content %}
{{ section.content | safe }}
<ul>
{% for page in section.pages %}
    <li><a href="{{ page.permalink }}">{{ page.title }}</a></li>
{% endfor %}
</ul>
{% endblock content %}
"""

    @staticmethod
    def _get_zola_page_template() -> str:
        """Get the page Tera template for a scaffolded Zola site."""
        return """{% extends "base.html" %}
{% block title %}{{ page.title }} - {{ config.title }}{% endblock title %}
{% block content %}
<article>
    <h1>{{ page.title }}</h1>
    {{ page.content | safe }}
</article>
{% endblock content %}
"""

    @staticmethod
    def _get_eleventy_config() -> str:
        """Get Eleventy configuration template.

        Returns
        -------
        str
            Eleventy .eleventy.js content

        """
        return """module.exports = function (eleventyConfig) {
  // Copy images straight through to the output directory
  eleventyConfig.addPassthroughCopy("src/images");

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
    },
    // Don't run converted Markdown through a template engine, which avoids
    // clashes with any literal {{ }} in the document content.
    markdownTemplateEngine: false,
  };
};
"""

    @staticmethod
    def _get_eleventy_package_json() -> str:
        """Get the package.json template for a scaffolded Eleventy site."""
        return """{
  "name": "my-site",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "eleventy",
    "serve": "eleventy --serve"
  },
  "devDependencies": {
    "@11ty/eleventy": "^3.0.0"
  }
}
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
        Target static site generator (Hugo, Jekyll, MkDocs, Zola, or Eleventy)
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
    if generator in (StaticSiteGenerator.HUGO, StaticSiteGenerator.ZOLA):
        # Hugo and Zola both serve the static/ directory at the site root.
        static_dir = output_dir / "static" / "images"
    elif generator == StaticSiteGenerator.MKDOCS:
        # MkDocs serves everything under docs/, so assets live there too.
        static_dir = output_dir / "docs" / "images"
    elif generator == StaticSiteGenerator.ELEVENTY:
        # Eleventy reads from src/ and passes src/images/ through to the output.
        static_dir = output_dir / "src" / "images"
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
            # Use root-relative path served by the generator
            if generator == StaticSiteGenerator.JEKYLL:
                # Jekyll serves assets/ at /assets/
                image.url = f"/assets/images/{dest_path.name}"
            else:
                # Hugo/Zola (static/images), MkDocs (docs/images), and Eleventy
                # (src/images via passthrough) all serve images at /images/
                image.url = f"/images/{dest_path.name}"

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

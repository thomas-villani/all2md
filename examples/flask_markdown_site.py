#!/usr/bin/env python3
"""Flask Markdown Site Server.

A simple Flask application that demonstrates how to build a markdown-powered
website using all2md. Features include:

- Automatic home page generation with post listing
- YAML frontmatter parsing for metadata
- URL slug generation
- Custom styling
- Static asset serving

Usage:
    python flask_markdown_site.py [--port PORT] [--content-dir PATH]

Example:
    python flask_markdown_site.py --port 8000 --content-dir ./my-content

Requirements:
    pip install flask all2md

"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, render_template_string, send_from_directory

from all2md import from_ast, to_ast
from all2md.options.html import HtmlRendererOptions


@dataclass
class Page:
    """Represents a parsed markdown page.

    Attributes
    ----------
    path : Path
        Filesystem path to the markdown file.
    url : str
        URL path for accessing the page.
    slug : str
        URL-friendly identifier for the page.
    title : str
        Page title from frontmatter or filename.
    content : str
        Rendered HTML content.
    date : datetime | None
        Publication date from frontmatter.
    author : str | None
        Author name from frontmatter.
    description : str | None
        Brief description from frontmatter.
    tags : list[str]
        List of tags from frontmatter.
    metadata : dict[str, Any]
        All frontmatter metadata.

    """

    path: Path
    url: str
    slug: str
    title: str
    content: str
    date: datetime | None
    author: str | None
    description: str | None
    tags: list[str]
    metadata: dict[str, Any]


class MarkdownSite:
    """Flask application for serving markdown content as HTML.

    Parameters
    ----------
    content_dir : Path
        Directory containing markdown files and assets.

    """

    def __init__(self, content_dir: Path) -> None:
        self.content_dir = content_dir
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Configure Flask routes."""
        self.app.route("/")(self.index)
        self.app.route("/<path:page_path>")(self.serve_page)
        self.app.route("/static/<path:filename>")(self.serve_static)

    def parse_markdown_file(self, path: Path) -> Page:
        """Parse a markdown file and extract metadata.

        Parameters
        ----------
        path : Path
            Path to the markdown file.

        Returns
        -------
        Page
            Parsed page object with content and metadata.

        """
        doc = to_ast(path)

        html_opts = HtmlRendererOptions(standalone=False)
        content = from_ast(doc, "html", renderer_options=html_opts)

        metadata = doc.metadata or {}

        title = metadata.get("title", path.stem.replace("-", " ").title())
        slug = metadata.get("slug", path.stem)

        relative_path = path.relative_to(self.content_dir)
        if relative_path.parent != Path("."):
            url = f"/{relative_path.parent}/{slug}"
        else:
            url = f"/{slug}"

        date_str = metadata.get("date") or metadata.get("creation_date")
        date = None
        if date_str:
            if isinstance(date_str, datetime):
                date = date_str
            elif isinstance(date_str, str):
                try:
                    date = datetime.fromisoformat(date_str)
                except ValueError:
                    pass

        return Page(
            path=path,
            url=url,
            slug=slug,
            title=title,
            content=content,
            date=date,
            author=metadata.get("author"),
            description=metadata.get("description"),
            tags=metadata.get("tags", []),
            metadata=metadata,
        )

    def get_blog_posts(self) -> list[Page]:
        """Get all blog posts sorted by date (most recent first).

        Returns
        -------
        list[Page]
            List of blog post pages sorted by date.

        """
        blog_dir = self.content_dir / "blog"
        if not blog_dir.exists():
            return []

        posts = []
        for md_file in blog_dir.glob("*.md"):
            page = self.parse_markdown_file(md_file)
            posts.append(page)

        posts.sort(key=lambda p: p.date or datetime.min, reverse=True)
        return posts

    def index(self) -> str:
        """Serve the home page with blog post listing.

        Returns
        -------
        str
            Rendered HTML for the home page.

        """
        posts = self.get_blog_posts()

        index_file = self.content_dir / "index.md"
        index_content = ""
        if index_file.exists():
            index_page = self.parse_markdown_file(index_file)
            index_content = index_page.content

        # nosemgrep: python.flask.security.audit.render-template-string.render-template-string
        # HTML_TEMPLATE is a static constant, not user-controlled input
        return render_template_string(HTML_TEMPLATE, title="Home", content=index_content, posts=posts, page=None)

    def serve_page(self, page_path: str) -> str:
        """Serve a markdown page as HTML.

        Parameters
        ----------
        page_path : str
            URL path to the page.

        Returns
        -------
        str
            Rendered HTML for the page.

        """
        md_file = self.content_dir / f"{page_path}.md"

        if not md_file.exists():
            parts = Path(page_path).parts
            if len(parts) > 1:
                parent = self.content_dir / parts[0]
                slug = parts[-1]
                for md_file_candidate in parent.glob("*.md"):
                    page = self.parse_markdown_file(md_file_candidate)
                    if page.slug == slug:
                        md_file = md_file_candidate
                        break

        if not md_file.exists() or not md_file.is_file():
            abort(404)

        page = self.parse_markdown_file(md_file)
        # nosemgrep: python.flask.security.audit.render-template-string.render-template-string
        # HTML_TEMPLATE is a static constant, not user-controlled input
        return render_template_string(HTML_TEMPLATE, title=page.title, content=page.content, posts=None, page=page)

    def serve_static(self, filename: str) -> Any:
        """Serve static assets from the content directory.

        Parameters
        ----------
        filename : str
            Name of the static file.

        Returns
        -------
        Any
            Flask response with the static file.

        """
        static_dir = self.content_dir / "static"
        return send_from_directory(static_dir, filename)

    def run(self, host: str = "127.0.0.1", port: int = 5000, debug: bool = True) -> None:
        """Start the Flask development server.

        Parameters
        ----------
        host : str, default='127.0.0.1'
            Host to bind to.
        port : int, default=5000
            Port to bind to.
        debug : bool, default=True
            Enable debug mode.

        """
        self.app.run(host=host, port=port, debug=debug)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <header>
        <nav>
            <h1><a href="/">My Markdown Site</a></h1>
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/about">About</a></li>
            </ul>
        </nav>
    </header>

    <main>
        {% if content %}
        <article>
            {{ content|safe }}
        </article>
        {% endif %}

        {% if page and page.date %}
        <aside class="metadata">
            <p class="date">Published: {{ page.date.strftime('%B %d, %Y') }}</p>
            {% if page.author %}
            <p class="author">By {{ page.author }}</p>
            {% endif %}
            {% if page.tags %}
            <p class="tags">
                Tags:
                {% for tag in page.tags %}
                <span class="tag">{{ tag }}</span>
                {% endfor %}
            </p>
            {% endif %}
        </aside>
        {% endif %}

        {% if posts %}
        <section class="posts">
            <h2>Recent Posts</h2>
            {% for post in posts %}
            <article class="post-card">
                <h3><a href="{{ post.url }}">{{ post.title }}</a></h3>
                {% if post.date %}
                <p class="post-date">{{ post.date.strftime('%B %d, %Y') }}</p>
                {% endif %}
                {% if post.description %}
                <p class="post-description">{{ post.description }}</p>
                {% endif %}
                {% if post.author %}
                <p class="post-author">By {{ post.author }}</p>
                {% endif %}
            </article>
            {% endfor %}
        </section>
        {% endif %}
    </main>

    <footer>
        <p>Powered by <a href="https://github.com/thomas-villani/all2md">all2md</a> and Flask</p>
    </footer>
</body>
</html>
"""


def main() -> None:
    """Run the Flask markdown site server."""
    parser = argparse.ArgumentParser(
        description="Flask Markdown Site Server - Serve markdown files as a website",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python flask_markdown_site.py
  python flask_markdown_site.py --port 8000
  python flask_markdown_site.py --content-dir ~/my-blog
        """,
    )
    parser.add_argument("--port", type=int, default=5000, help="Port to run the server on (default: 5000)")
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=Path(__file__).parent / "flask-site-content",
        help="Directory containing markdown files (default: ./flask-site-content)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")

    args = parser.parse_args()

    if not args.content_dir.exists():
        print(f"Error: Content directory '{args.content_dir}' does not exist.")
        print("Please create it and add some markdown files, or specify a different directory with --content-dir")
        return

    site = MarkdownSite(args.content_dir)
    print(f"Starting server on http://{args.host}:{args.port}")
    print(f"Serving content from: {args.content_dir.absolute()}")
    print("Press Ctrl+C to stop")
    site.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

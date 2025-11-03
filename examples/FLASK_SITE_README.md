# Flask Markdown Site Example

A simple Flask application that demonstrates how to build a markdown-powered website using **all2md**. This example showcases automatic post listing, YAML frontmatter parsing, URL slug generation, and custom styling.

## Features

- **Automatic Home Page Generation** - Scans blog directory and displays posts sorted by date
- **YAML Frontmatter Parsing** - Extracts metadata (title, date, author, tags, description)
- **URL Slug Support** - Clean URLs from frontmatter slugs or filenames
- **Custom Styling** - Responsive CSS with modern design
- **Static Asset Serving** - Serves images and CSS from content directory
- **Dynamic HTML Rendering** - Converts markdown to HTML on-the-fly

## Installation

First, install the required dependencies:

```bash
pip install flask all2md
```

## Quick Start

Run the Flask application with the included sample content:

```bash
python examples/flask_markdown_site.py
```

Then open your browser to [http://localhost:5000](http://localhost:5000)

## Usage

### Basic Usage

```bash
# Run on default port 5000
python flask_markdown_site.py

# Run on custom port
python flask_markdown_site.py --port 8000

# Use custom content directory
python flask_markdown_site.py --content-dir /path/to/content

# Bind to all interfaces (for network access)
python flask_markdown_site.py --host 0.0.0.0
```

### Command-Line Options

- `--port PORT` - Port to run the server on (default: 5000)
- `--content-dir PATH` - Directory containing markdown files (default: ./flask-site-content)
- `--host HOST` - Host to bind to (default: 127.0.0.1)

## Content Structure

The example expects the following directory structure:

```
flask-site-content/
├── index.md                 # Home page content
├── about.md                 # About page
├── blog/                    # Blog posts directory
│   ├── post1.md
│   ├── post2.md
│   └── post3.md
└── static/                  # Static assets
    └── style.css            # Stylesheet
```

## Frontmatter Format

Each markdown file can include YAML frontmatter with metadata:

```yaml
---
title: "Post Title"
date: 2025-01-29
author: "Author Name"
slug: "custom-url-slug"
description: "Brief description for post listing"
tags: ["python", "markdown", "tutorial"]
---

# Your Markdown Content Here

Regular markdown content...
```

### Supported Frontmatter Fields

- `title` - Page title (defaults to filename if not specified)
- `date` - Publication date in ISO format (YYYY-MM-DD)
- `author` - Author name
- `slug` - Custom URL slug (defaults to filename)
- `description` - Brief description shown in post listings
- `tags` - List of tags

**Note:** all2md normalizes the `date` field to `creation_date` internally, but the application handles both.

## How It Works

### 1. Markdown Parsing

The application uses all2md's `to_ast()` function to parse markdown files:

```python
from all2md import to_ast

doc = to_ast("content.md")
metadata = doc.metadata  # Access frontmatter
```

### 2. HTML Rendering

Markdown is converted to HTML using `from_ast()`:

```python
from all2md import from_ast
from all2md.options.html import HtmlRendererOptions

html_opts = HtmlRendererOptions(standalone=False)
html = from_ast(doc, "html", renderer_options=html_opts)
```

### 3. Post Listing

The home page automatically generates a post listing:

1. Scans the `blog/` directory for markdown files
2. Parses each file to extract frontmatter
3. Sorts posts by date (most recent first)
4. Displays with metadata (title, date, author, description)

### 4. URL Routing

Flask routes map URLs to markdown files:

- `/` - Home page with post listing
- `/about` - Static page from about.md
- `/blog/post-slug` - Blog post from blog/post-slug.md

## Customization

### Styling

Edit `flask-site-content/static/style.css` to customize the appearance. The included stylesheet features:

- Responsive design for mobile and desktop
- GitHub-like markdown styling
- Clean, modern aesthetics
- Code syntax highlighting support

### Template

The HTML template is embedded in `flask_markdown_site.py`. To customize:

1. Edit the `HTML_TEMPLATE` variable
2. Use Jinja2 template syntax
3. Available variables:
   - `title` - Page title
   - `content` - Rendered HTML content
   - `posts` - List of blog posts (on home page)
   - `page` - Current page metadata

### Adding Content

To add new content:

1. Create a new markdown file in `flask-site-content/` or `flask-site-content/blog/`
2. Add YAML frontmatter with metadata
3. Write your markdown content
4. The file will be automatically served at `/<filename>` or `/blog/<filename>`

## Development

The application runs in debug mode by default, which enables:

- Automatic reloading when code changes
- Detailed error messages
- Development server warnings

For production deployment, see [Flask deployment documentation](https://flask.palletsprojects.com/en/latest/deploying/).

## Code Overview

### Main Components

**MarkdownSite Class**
- `parse_markdown_file()` - Parses markdown and extracts metadata
- `get_blog_posts()` - Returns all blog posts sorted by date
- `index()` - Serves home page with post listing
- `serve_page()` - Serves individual pages
- `serve_static()` - Serves static assets

**Page Dataclass**
- Represents a parsed markdown page
- Contains path, URL, title, content, metadata

**HTML Template**
- Embedded Jinja2 template
- Renders content with navigation and metadata

## Troubleshooting

### Flask Not Found

If you see `ModuleNotFoundError: No module named 'flask'`:

```bash
pip install flask
```

### Content Directory Not Found

If you see "Content directory does not exist":

```bash
# Specify the correct path
python flask_markdown_site.py --content-dir ./path/to/content
```

### Port Already in Use

If port 5000 is already in use:

```bash
python flask_markdown_site.py --port 8000
```

### Static Files Not Loading

Ensure your content directory has a `static/` subdirectory with `style.css`.

## Example Output

Running the application with the sample content will display:

- **Home Page** - Welcome content and list of 3 blog posts
- **Blog Posts** - Three sample posts demonstrating different features
- **About Page** - Information about the site and all2md

## Related Examples

Check out other examples in the `examples/` directory:

- `batch_converter.py` - Bulk document conversion
- `jinja_template_demo.py` - Custom Jinja2 template rendering
- `vcs-converter/` - Git integration example

## License

This example is part of the all2md project. See the main LICENSE file for details.

## Links

- [all2md Documentation](https://github.com/tconbeer/all2md)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Markdown Guide](https://www.markdownguide.org/)

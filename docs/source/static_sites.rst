Static Site Generation
======================

all2md includes a powerful ``generate-site`` command that converts document collections into production-ready Hugo or Jekyll static sites. The command handles frontmatter generation, asset copying, directory scaffolding, and metadata mapping, enabling you to transform documentation folders or blog posts into fully-functional static sites.

.. contents::
   :local:
   :depth: 2

Overview
--------

The ``generate-site`` command is purpose-built for creating static sites from document collections. Unlike the HTML template-based approach (which remains available for custom HTML generation), ``generate-site`` produces complete Hugo or Jekyll site structures with proper frontmatter, asset organization, and configuration files.

Key Features
~~~~~~~~~~~~

- **Hugo and Jekyll Support** - Target either static site generator with appropriate directory structures and frontmatter formats
- **Automatic Frontmatter** - Intelligently maps document metadata to frontmatter fields (title, date, author, tags, categories)
- **Asset Management** - Collects images from documents, copies them to the correct static directories, and updates references
- **Scaffolding** - Optionally creates complete site structures with config files and layout templates
- **Batch Processing** - Recursively process entire directories with file exclusion patterns
- **Flexible Output** - Control content subdirectories, frontmatter formats, and file naming conventions

When to Use generate-site
~~~~~~~~~~~~~~~~~~~~~~~~~~

Choose ``generate-site`` when you want to:

- Convert documentation folders to Hugo or Jekyll sites
- Migrate blog posts to a static site generator
- Create a documentation site from markdown files
- Build a knowledge base with proper categorization
- Maintain content in simple markdown while publishing to a static site

For custom HTML generation with full template control, see the :doc:`api/all2md.renderers.html` HTML renderer documentation.

Quick Start
-----------

Basic Hugo Example
~~~~~~~~~~~~~~~~~~

Convert a documentation folder to a Hugo site:

.. code-block:: bash

   # Create a complete Hugo site with scaffolding
   all2md generate-site docs/ \
       --output-dir my-hugo-site \
       --generator hugo \
       --scaffold \
       --recursive

   # Result:
   # my-hugo-site/
   # ├── config.toml
   # ├── content/
   # │   ├── _index.md
   # │   ├── getting-started.md
   # │   └── api-reference.md
   # ├── static/images/
   # │   └── (copied images)
   # ├── themes/
   # ├── layouts/
   # └── data/

Basic Jekyll Example
~~~~~~~~~~~~~~~~~~~~~

Convert blog posts to a Jekyll site:

.. code-block:: bash

   # Create a complete Jekyll blog with scaffolding
   all2md generate-site posts/ \
       --output-dir my-blog \
       --generator jekyll \
       --scaffold \
       --recursive

   # Result:
   # my-blog/
   # ├── _config.yml
   # ├── _posts/
   # │   ├── 2025-01-22-welcome.md
   # │   └── 2025-01-20-first-post.md
   # ├── assets/images/
   # │   └── (copied images)
   # ├── _layouts/
   # │   ├── default.html
   # │   └── post.html
   # └── _includes/

Command Syntax
~~~~~~~~~~~~~~

.. code-block:: bash

   all2md generate-site INPUT... \
       --output-dir DIR \
       --generator {hugo|jekyll} \
       [--scaffold] \
       [--frontmatter-format {yaml|toml}] \
       [--content-subdir PATH] \
       [--recursive] \
       [--exclude PATTERN]

The generate-site Command
--------------------------

Command Reference
~~~~~~~~~~~~~~~~~

**Required Arguments:**

``INPUT...``
   One or more input files or directories to convert. Can be specific files (``posts/welcome.md posts/intro.md``) or directories (``docs/``).

``--output-dir DIR``
   Output directory for the generated site. Will be created if it doesn't exist.

``--generator {hugo|jekyll}``
   Target static site generator. Determines directory structure, frontmatter defaults, and asset paths.

**Optional Arguments:**

``--scaffold``
   Create complete site structure including config files, layouts, and directory placeholders. Without this flag, only the content and static assets are generated.

``--frontmatter-format {yaml|toml}``
   Override default frontmatter format. Hugo defaults to TOML (``+++`` delimiters), Jekyll to YAML (``---`` delimiters).

``--content-subdir PATH``
   Subdirectory within the content directory for output files. For example, ``--content-subdir posts`` with Hugo creates files in ``content/posts/``.

``--recursive``
   Recursively process directories, converting all found documents.

``--exclude PATTERN``
   Exclude files matching the pattern. Can be specified multiple times for multiple patterns. Supports glob patterns.

Usage Examples
~~~~~~~~~~~~~~

**Content Only (No Scaffolding):**

.. code-block:: bash

   # Just convert documents, don't create config/layouts
   all2md generate-site reports/*.pdf \
       --output-dir hugo-reports \
       --generator hugo

**Custom Content Subdirectory:**

.. code-block:: bash

   # Place output in content/blog/ instead of content/
   all2md generate-site posts/ \
       --output-dir my-site \
       --generator hugo \
       --content-subdir blog \
       --recursive

**With File Exclusions:**

.. code-block:: bash

   # Skip drafts and private files
   all2md generate-site content/ \
       --output-dir site \
       --generator jekyll \
       --recursive \
       --exclude "draft-*" \
       --exclude "private/*" \
       --exclude "*.tmp"

**Custom Frontmatter Format:**

.. code-block:: bash

   # Use YAML frontmatter with Hugo (instead of default TOML)
   all2md generate-site docs/ \
       --output-dir hugo-site \
       --generator hugo \
       --frontmatter-format yaml \
       --scaffold

Hugo Static Sites
-----------------

Hugo Overview
~~~~~~~~~~~~~

Hugo is a fast, flexible static site generator written in Go. It uses a content-centric approach with markdown files in the ``content/`` directory and places static assets in ``static/``.

**Standard Hugo Directory Structure:**

.. code-block:: text

   hugo-site/
   ├── config.toml          # Site configuration
   ├── content/             # Markdown content files
   │   ├── _index.md        # Homepage content
   │   └── posts/           # Post subdirectories (optional)
   ├── static/              # Static assets (images, CSS, JS)
   │   └── images/          # Image files
   ├── themes/              # Theme directory
   ├── layouts/             # Custom templates
   └── data/                # Data files

Generating a Hugo Site
~~~~~~~~~~~~~~~~~~~~~~

**With Scaffolding:**

.. code-block:: bash

   # Create complete Hugo site structure
   all2md generate-site documentation/ \
       --output-dir my-docs \
       --generator hugo \
       --scaffold \
       --recursive

This creates:

- ``config.toml`` with basic site configuration
- ``content/_index.md`` homepage placeholder
- Empty ``themes/``, ``layouts/``, and ``data/`` directories
- Converted markdown files in ``content/``
- Copied images in ``static/images/``

**Without Scaffolding:**

.. code-block:: bash

   # Only convert content and copy assets
   all2md generate-site docs/*.md \
       --output-dir my-docs \
       --generator hugo

This creates only:

- Converted markdown files in ``content/``
- Copied images in ``static/images/``

Hugo Frontmatter
~~~~~~~~~~~~~~~~

By default, Hugo uses TOML frontmatter with ``+++`` delimiters:

.. code-block:: toml

   +++
   title = "Getting Started with all2md"
   date = 2025-01-22T10:00:00
   author = "Jane Developer"
   description = "A comprehensive guide to document conversion"
   tags = ["tutorial", "documentation", "beginner"]
   draft = false
   weight = 10
   +++

**Metadata Mapping:**

The command automatically maps document metadata to Hugo frontmatter:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Hugo Field
     - Source Metadata
   * - ``title``
     - Document ``title`` metadata or filename
   * - ``date``
     - ``creation_date``, ``date``, or ``modified`` metadata (ISO 8601 format)
   * - ``author``
     - ``author`` metadata
   * - ``description``
     - ``description`` or ``subject`` metadata
   * - ``tags``
     - ``tags`` or ``keywords`` metadata (comma-separated or list)
   * - ``draft``
     - Always set to ``false``
   * - ``weight``
     - ``weight`` metadata (Hugo-specific, for sorting)

**YAML Frontmatter with Hugo:**

You can use YAML frontmatter with Hugo by specifying the format:

.. code-block:: bash

   all2md generate-site docs/ \
       --output-dir hugo-site \
       --generator hugo \
       --frontmatter-format yaml

Result:

.. code-block:: yaml

   ---
   title: Getting Started with all2md
   date: 2025-01-22 10:00:00
   author: Jane Developer
   description: A comprehensive guide to document conversion
   tags:
     - tutorial
     - documentation
     - beginner
   draft: false
   weight: 10
   ---

Hugo Asset Organization
~~~~~~~~~~~~~~~~~~~~~~~

Images and other assets are copied to ``static/images/`` and referenced with the ``/images/`` path prefix:

**Before conversion** (in source document):

.. code-block:: markdown

   ![Architecture Diagram](./diagrams/architecture.png)

**After conversion** (in Hugo content):

.. code-block:: markdown

   ![Architecture Diagram](/images/architecture.png)

The actual file is copied to ``static/images/architecture.png``.

**Asset Handling:**

- **Local files** - Copied to ``static/images/`` with sanitized filenames
- **Data URIs** - Left unchanged (``data:image/png;base64,...``)
- **Remote URLs** - Left unchanged (``https://example.com/image.png``)
- **Duplicate names** - Automatically made unique with suffixes

Jekyll Static Sites
-------------------

Jekyll Overview
~~~~~~~~~~~~~~~

Jekyll is a Ruby-based static site generator that emphasizes convention over configuration. It uses markdown files in ``_posts/`` for blog posts and places static assets in ``assets/``.

**Standard Jekyll Directory Structure:**

.. code-block:: text

   jekyll-site/
   ├── _config.yml          # Site configuration
   ├── _posts/              # Blog posts (with date-prefixed names)
   │   ├── 2025-01-22-welcome.md
   │   └── 2025-01-20-intro.md
   ├── assets/              # Static assets
   │   └── images/          # Image files
   ├── _layouts/            # Page templates
   │   ├── default.html
   │   └── post.html
   └── _includes/           # Reusable template fragments

Generating a Jekyll Site
~~~~~~~~~~~~~~~~~~~~~~~~~

**With Scaffolding:**

.. code-block:: bash

   # Create complete Jekyll site structure
   all2md generate-site posts/ \
       --output-dir my-blog \
       --generator jekyll \
       --scaffold \
       --recursive

This creates:

- ``_config.yml`` with basic site configuration
- ``_layouts/default.html`` and ``_layouts/post.html`` templates
- ``_includes/`` directory for template fragments
- Converted markdown files in ``_posts/`` with date prefixes
- Copied images in ``assets/images/``

**Without Scaffolding:**

.. code-block:: bash

   # Only convert content and copy assets
   all2md generate-site posts/*.md \
       --output-dir my-blog \
       --generator jekyll

This creates only:

- Converted markdown files in ``_posts/``
- Copied images in ``assets/images/``

Jekyll Frontmatter
~~~~~~~~~~~~~~~~~~

By default, Jekyll uses YAML frontmatter with ``---`` delimiters:

.. code-block:: yaml

   ---
   title: Getting Started with all2md
   date: 2025-01-22 10:00:00
   author: Jane Developer
   description: A comprehensive guide to document conversion
   categories:
     - tutorial
     - documentation
   layout: post
   permalink: /getting-started/
   ---

**Metadata Mapping:**

The command automatically maps document metadata to Jekyll frontmatter:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Jekyll Field
     - Source Metadata
   * - ``title``
     - Document ``title`` metadata or filename
   * - ``date``
     - ``creation_date``, ``date``, or ``modified`` metadata (ISO 8601 format)
   * - ``author``
     - ``author`` metadata
   * - ``description``
     - ``description`` or ``subject`` metadata
   * - ``categories``
     - ``categories`` or ``category`` metadata (comma-separated or list)
   * - ``layout``
     - Always set to ``post``
   * - ``permalink``
     - ``permalink`` metadata (Jekyll-specific, for custom URLs)

**TOML Frontmatter with Jekyll:**

You can use TOML frontmatter with Jekyll by specifying the format:

.. code-block:: bash

   all2md generate-site posts/ \
       --output-dir jekyll-site \
       --generator jekyll \
       --frontmatter-format toml

Result:

.. code-block:: toml

   +++
   title = "Getting Started with all2md"
   date = 2025-01-22T10:00:00
   author = "Jane Developer"
   description = "A comprehensive guide to document conversion"
   categories = ["tutorial", "documentation"]
   layout = "post"
   permalink = "/getting-started/"
   +++

Jekyll Asset Organization
~~~~~~~~~~~~~~~~~~~~~~~~~~

Images and other assets are copied to ``assets/images/`` and referenced with the ``/assets/images/`` path prefix:

**Before conversion** (in source document):

.. code-block:: markdown

   ![Screenshot](./screenshots/login.png)

**After conversion** (in Jekyll content):

.. code-block:: markdown

   ![Screenshot](/assets/images/login.png)

The actual file is copied to ``assets/images/login.png``.

**Asset Handling:**

- **Local files** - Copied to ``assets/images/`` with sanitized filenames
- **Data URIs** - Left unchanged (``data:image/png;base64,...``)
- **Remote URLs** - Left unchanged (``https://example.com/image.png``)
- **Duplicate names** - Automatically made unique with suffixes

Jekyll Date-Prefixed Filenames
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Jekyll requires blog posts to use date-prefixed filenames in the format ``YYYY-MM-DD-title.md``. The ``generate-site`` command automatically handles this:

**If the document has date metadata:**

.. code-block:: bash

   # Source: getting-started.md with metadata: date: 2025-01-22
   # Output: _posts/2025-01-22-getting-started.md

**If the document has no date metadata:**

.. code-block:: bash

   # Source: tutorial.md (no date metadata)
   # Output: _posts/tutorial.md (no date prefix)

Frontmatter Generation
-----------------------

Metadata Mapping
~~~~~~~~~~~~~~~~

The command intelligently extracts metadata from source documents and maps it to appropriate frontmatter fields. The mapping is smart enough to handle various metadata field names and formats.

**Title Extraction:**

1. ``title`` metadata field
2. Document filename (without extension) as fallback

**Date Extraction:**

1. ``creation_date`` metadata field (highest priority)
2. ``date`` metadata field
3. ``modified`` metadata field
4. No date if none found

**Author Extraction:**

1. ``author`` metadata field
2. Not included if missing

**Description Extraction:**

1. ``description`` metadata field
2. ``subject`` metadata field (fallback)
3. Not included if missing

**Tags Extraction (Hugo):**

1. ``tags`` metadata field (can be list or comma-separated string)
2. ``keywords`` metadata field (comma-separated string)
3. Empty list if missing

**Categories Extraction (Jekyll):**

1. ``categories`` metadata field (can be list or comma-separated string)
2. ``category`` metadata field (single category or comma-separated string)
3. Empty list if missing

**Example Metadata:**

.. code-block:: yaml

   # In source document metadata
   title: Advanced Python Techniques
   author: Sarah Developer
   creation_date: 2025-01-22T14:30:00
   keywords: python, programming, advanced, tips
   description: Learn advanced Python techniques for cleaner code

**Resulting Hugo Frontmatter (TOML):**

.. code-block:: toml

   +++
   title = "Advanced Python Techniques"
   date = 2025-01-22T14:30:00
   author = "Sarah Developer"
   description = "Learn advanced Python techniques for cleaner code"
   tags = ["python", "programming", "advanced", "tips"]
   draft = false
   +++

**Resulting Jekyll Frontmatter (YAML):**

.. code-block:: yaml

   ---
   title: Advanced Python Techniques
   date: 2025-01-22 14:30:00
   author: Sarah Developer
   description: Learn advanced Python techniques for cleaner code
   categories:
     - python
     - programming
     - advanced
     - tips
   layout: post
   ---

Format Comparison
~~~~~~~~~~~~~~~~~

YAML and TOML are both popular frontmatter formats with different syntax:

**YAML Format (``---`` delimiters):**

.. code-block:: yaml

   ---
   title: My Article
   date: 2025-01-22
   tags:
     - tutorial
     - beginner
   nested:
     key: value
   ---

Advantages:

- More readable for complex nested structures
- Native list syntax
- Jekyll default
- Wide tool support

**TOML Format (``+++`` delimiters):**

.. code-block:: toml

   +++
   title = "My Article"
   date = 2025-01-22T00:00:00
   tags = ["tutorial", "beginner"]

   [nested]
   key = "value"
   +++

Advantages:

- More explicit with quotation
- Hugo default
- Strongly typed
- Better date/time handling

String Escaping
~~~~~~~~~~~~~~~

The frontmatter generator automatically handles string escaping:

**YAML:**

Quotes strings containing special characters (``:``, ``#``, ``{``, ``}``, etc.):

.. code-block:: yaml

   title: "Advanced: Python Tips"  # Colon requires quotes
   description: This is a simple title  # No special chars, no quotes

**TOML:**

Escapes inner quotes with backslashes:

.. code-block:: toml

   title = "Book: \"Python Patterns\""  # Inner quotes escaped
   description = "A comprehensive guide"  # Normal strings quoted

Asset Management
----------------

Image Collection
~~~~~~~~~~~~~~~~

The ``generate-site`` command automatically finds all images in your documents by walking the Abstract Syntax Tree (AST). This ensures no images are missed regardless of how they're embedded in the markdown structure.

**Images Are Collected From:**

- Standard markdown image syntax: ``![alt](path)``
- Images in tables
- Images in lists
- Images in nested block structures
- Reference-style images

**Images Are NOT Collected:**

- Data URIs (``data:image/png;base64,...``) - left unchanged in markdown
- Remote URLs (``http://`` or ``https://``) - left unchanged in markdown

File Copying
~~~~~~~~~~~~

After collection, local image files are:

1. **Sanitized** - Filenames are cleaned to be filesystem-safe
2. **Uniquified** - Duplicate names get numeric suffixes (``image.png``, ``image-1.png``, ``image-2.png``)
3. **Copied** - Files are physically copied to the static directory
4. **Referenced** - Markdown is updated with the new path

**Sanitization Example:**

.. code-block:: text

   Original:    My Diagram (2024).png
   Sanitized:   My-Diagram-2024.png

**Uniqueness Example:**

.. code-block:: text

   diagram.png      → /images/diagram.png
   diagram.png      → /images/diagram-1.png
   diagram.png      → /images/diagram-2.png

**Path Updates:**

The markdown is automatically updated to reference the new location:

.. code-block:: markdown

   # Before
   ![Chart](../assets/sales-chart.png)
   ![Photo](./photos/team.jpg)

   # After (Hugo)
   ![Chart](/images/sales-chart.png)
   ![Photo](/images/team.jpg)

   # After (Jekyll)
   ![Chart](/assets/images/sales-chart.png)
   ![Photo](/assets/images/team.jpg)

Generator-Specific Paths
~~~~~~~~~~~~~~~~~~~~~~~~~

**Hugo:**

- Static directory: ``static/images/``
- Markdown reference: ``/images/filename``

**Jekyll:**

- Static directory: ``assets/images/``
- Markdown reference: ``/assets/images/filename``

Output File Naming
------------------

The command generates output filenames using a intelligent fallback strategy:

Slugification from Titles
~~~~~~~~~~~~~~~~~~~~~~~~~~

If the document has a ``title`` metadata field, it is converted to a URL-safe slug:

.. code-block:: text

   Title: "Getting Started with Python"
   Output: getting-started-with-python.md

   Title: "API Reference: Version 2.0"
   Output: api-reference-version-2-0.md

**Slugification Rules:**

1. Convert to lowercase
2. Replace spaces and special characters with hyphens
3. Remove consecutive hyphens
4. Remove leading/trailing hyphens

Fallback to Source Filenames
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If no ``title`` metadata exists, the source filename (without extension) is used:

.. code-block:: text

   Source: my-document.pdf
   Output: my-document.md

   Source: 2024-Q4-Report.docx
   Output: 2024-q4-report.md

Jekyll Date Prefixes
~~~~~~~~~~~~~~~~~~~~~

For Jekyll, if the document has date metadata (``creation_date``, ``date``, or ``modified``), the date is prepended in ``YYYY-MM-DD`` format:

.. code-block:: text

   # With date metadata: 2025-01-22
   Title: "Welcome Post"
   Output: 2025-01-22-welcome-post.md

   # Without date metadata
   Title: "About Page"
   Output: about-page.md

**Hugo does not use date prefixes** - filenames are based solely on title or source filename.

Index-Based Fallback
~~~~~~~~~~~~~~~~~~~~~

If both title and filename are unusable (e.g., invalid characters), an index-based name is used:

.. code-block:: text

   Output: document-0.md
   Output: document-1.md
   Output: document-2.md

Batch Processing
----------------

The ``--recursive`` flag enables batch processing of entire directory trees:

Recursive Directory Scanning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process all markdown and PDF files in docs/ and subdirectories
   all2md generate-site docs/ \
       --output-dir hugo-site \
       --generator hugo \
       --recursive

This will:

1. Scan ``docs/`` and all subdirectories
2. Detect all convertible file types
3. Convert each document
4. Preserve relative directory structure (optional)

File Exclusion Patterns
~~~~~~~~~~~~~~~~~~~~~~~~

Use ``--exclude`` to skip files matching specific patterns:

.. code-block:: bash

   # Skip drafts, private files, and temporary files
   all2md generate-site content/ \
       --output-dir site \
       --generator jekyll \
       --recursive \
       --exclude "draft-*" \
       --exclude "private/*" \
       --exclude "*.tmp" \
       --exclude "README.md"

**Glob Patterns Supported:**

- ``*.tmp`` - All .tmp files
- ``draft-*`` - Files starting with "draft-"
- ``private/*`` - Everything in private/ subdirectory
- ``README.md`` - Specific file

Integration with CLI Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``generate-site`` command works seamlessly with other all2md CLI features:

.. code-block:: bash

   # Use with format-specific options
   all2md generate-site reports/*.pdf \
       --output-dir site \
       --generator hugo \
       --pdf-pages "1-10" \
       --attachment-mode download

   # Use with transforms
   all2md generate-site docs/ \
       --output-dir site \
       --generator jekyll \
       --recursive \
       --transform add-heading-ids \
       --transform add-toc

Scaffolding
-----------

Hugo Scaffolding
~~~~~~~~~~~~~~~~

With ``--scaffold``, a complete Hugo site structure is created:

**Directory Structure:**

.. code-block:: text

   output-dir/
   ├── config.toml          # Site configuration
   ├── content/             # Content directory
   │   └── _index.md        # Homepage placeholder
   ├── static/              # Static assets
   │   └── images/          # Image directory
   ├── themes/              # Themes directory (empty)
   ├── layouts/             # Custom layouts (empty)
   └── data/                # Data files (empty)

**config.toml Contents:**

.. code-block:: toml

   baseURL = "https://example.com/"
   languageCode = "en-us"
   title = "My Site"
   theme = ""

   [params]
   description = "Site description"

**content/_index.md Contents:**

.. code-block:: markdown

   +++
   title = "Home"
   draft = false
   +++

   # Welcome

   This is the homepage.

**Building the Site:**

After generating the scaffolded structure:

.. code-block:: bash

   cd output-dir
   hugo server  # Start development server
   hugo         # Build for production

Jekyll Scaffolding
~~~~~~~~~~~~~~~~~~

With ``--scaffold``, a complete Jekyll site structure is created:

**Directory Structure:**

.. code-block:: text

   output-dir/
   ├── _config.yml          # Site configuration
   ├── _posts/              # Posts directory
   ├── assets/              # Static assets
   │   └── images/          # Image directory
   ├── _layouts/            # Layout templates
   │   ├── default.html
   │   └── post.html
   └── _includes/           # Template fragments (empty)

**_config.yml Contents:**

.. code-block:: yaml

   title: My Site
   description: Site description
   baseurl: ""
   url: "https://example.com"

   markdown: kramdown
   permalink: /:year/:month/:day/:title/

   plugins:
     - jekyll-feed
     - jekyll-seo-tag

**_layouts/default.html Contents:**

.. code-block:: html

   <!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{{ page.title }} | {{ site.title }}</title>
   </head>
   <body>
       <header>
           <h1><a href="/">{{ site.title }}</a></h1>
       </header>

       <main>
           {{ content }}
       </main>

       <footer>
           <p>&copy; 2025 {{ site.title }}</p>
       </footer>
   </body>
   </html>

**_layouts/post.html Contents:**

.. code-block:: html

   ---
   layout: default
   ---

   <article>
       <header>
           <h1>{{ page.title }}</h1>
           <p class="meta">
               {% if page.author %}By {{ page.author }} | {% endif %}
               {{ page.date | date: "%B %d, %Y" }}
           </p>
       </header>

       <div class="content">
           {{ content }}
       </div>
   </article>

**Building the Site:**

After generating the scaffolded structure:

.. code-block:: bash

   cd output-dir
   bundle exec jekyll serve  # Start development server
   bundle exec jekyll build  # Build for production

Complete Examples
-----------------

Convert Documentation Folder to Hugo Site
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Scenario:** You have a ``docs/`` folder with markdown files and PDF reports that you want to convert to a Hugo documentation site.

**Directory Structure (Before):**

.. code-block:: text

   docs/
   ├── index.md
   ├── getting-started.md
   ├── api/
   │   ├── authentication.md
   │   └── endpoints.md
   ├── tutorials/
   │   ├── tutorial-1.pdf
   │   └── tutorial-2.docx
   └── images/
       └── logo.png

**Command:**

.. code-block:: bash

   all2md generate-site docs/ \
       --output-dir my-hugo-docs \
       --generator hugo \
       --scaffold \
       --recursive \
       --exclude "images/*"

**Directory Structure (After):**

.. code-block:: text

   my-hugo-docs/
   ├── config.toml
   ├── content/
   │   ├── _index.md
   │   ├── index.md
   │   ├── getting-started.md
   │   ├── api/
   │   │   ├── authentication.md
   │   │   └── endpoints.md
   │   └── tutorials/
   │       ├── tutorial-1.md      # Converted from PDF
   │       └── tutorial-2.md      # Converted from DOCX
   ├── static/
   │   └── images/
   │       └── logo.png            # Copied from source
   ├── themes/
   ├── layouts/
   └── data/

**Sample Converted File (content/getting-started.md):**

.. code-block:: markdown

   +++
   title = "Getting Started Guide"
   date = 2025-01-22T10:00:00
   author = "Documentation Team"
   description = "Quick start guide for new users"
   tags = ["tutorial", "beginner"]
   draft = false
   +++

   # Getting Started

   Welcome to our product! This guide will help you get up and running.

   ![Logo](/images/logo.png)

   ## Installation

   Follow these steps to install...

**Building the Site:**

.. code-block:: bash

   cd my-hugo-docs
   hugo server -D  # Preview at http://localhost:1313

Convert Blog Posts to Jekyll Site
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Scenario:** You have blog posts as markdown files with frontmatter metadata that you want to convert to a Jekyll blog.

**Directory Structure (Before):**

.. code-block:: text

   posts/
   ├── welcome.md
   ├── first-tutorial.md
   ├── advanced-tips.md
   └── images/
       ├── welcome-banner.png
       └── tutorial-screenshot.png

**Sample Source File (posts/welcome.md):**

.. code-block:: markdown

   ---
   title: Welcome to My Blog
   author: Jane Blogger
   creation_date: 2025-01-22T09:00:00
   keywords: blog, welcome, introduction
   description: Welcome post introducing my new blog
   ---

   # Welcome!

   This is my first blog post...

   ![Banner](./images/welcome-banner.png)

**Command:**

.. code-block:: bash

   all2md generate-site posts/ \
       --output-dir my-jekyll-blog \
       --generator jekyll \
       --scaffold \
       --recursive \
       --exclude "images/*"

**Directory Structure (After):**

.. code-block:: text

   my-jekyll-blog/
   ├── _config.yml
   ├── _posts/
   │   ├── 2025-01-22-welcome.md
   │   ├── first-tutorial.md
   │   └── advanced-tips.md
   ├── assets/
   │   └── images/
   │       ├── welcome-banner.png
   │       └── tutorial-screenshot.png
   ├── _layouts/
   │   ├── default.html
   │   └── post.html
   └── _includes/

**Sample Converted File (_posts/2025-01-22-welcome.md):**

.. code-block:: markdown

   ---
   title: Welcome to My Blog
   date: 2025-01-22 09:00:00
   author: Jane Blogger
   description: Welcome post introducing my new blog
   categories:
     - blog
     - welcome
     - introduction
   layout: post
   ---

   # Welcome!

   This is my first blog post...

   ![Banner](/assets/images/welcome-banner.png)

**Building the Site:**

.. code-block:: bash

   cd my-jekyll-blog
   bundle exec jekyll serve  # Preview at http://localhost:4000

Migration Workflows
~~~~~~~~~~~~~~~~~~~

**PDF Reports to Hugo Documentation:**

.. code-block:: bash

   # Convert quarterly reports to a Hugo docs site
   all2md generate-site reports/*.pdf \
       --output-dir company-docs \
       --generator hugo \
       --content-subdir reports \
       --scaffold \
       --pdf-pages "1-10"  # Only first 10 pages

**DOCX Policies to Jekyll Knowledge Base:**

.. code-block:: bash

   # Convert policy documents to a searchable Jekyll site
   all2md generate-site policies/ \
       --output-dir kb-site \
       --generator jekyll \
       --scaffold \
       --recursive \
       --exclude "templates/*" \
       --exclude "drafts/*"

**Mixed Format Archives to Hugo:**

.. code-block:: bash

   # Convert docs from multiple formats
   all2md generate-site archives/ \
       --output-dir unified-docs \
       --generator hugo \
       --scaffold \
       --recursive

API Reference
-------------

The ``generate-site`` command is powered by utilities in the ``all2md.utils.static_site`` module:

Python API
~~~~~~~~~~

You can use these utilities directly in Python code:

.. code-block:: python

   from pathlib import Path
   from all2md import to_ast
   from all2md.utils.static_site import (
       StaticSiteGenerator,
       FrontmatterFormat,
       FrontmatterGenerator,
       SiteScaffolder,
       ImageCollector,
       copy_document_assets,
       generate_output_filename,
   )

   # Parse a document
   doc = to_ast('document.md')

   # Generate frontmatter
   fm_gen = FrontmatterGenerator(
       generator=StaticSiteGenerator.HUGO,
       format=FrontmatterFormat.TOML
   )
   frontmatter = fm_gen.generate(doc.metadata)

   # Collect images
   collector = ImageCollector()
   collector.collect(doc)
   print(f"Found {len(collector.images)} images")

   # Copy assets and update document
   output_dir = Path('my-site')
   modified_doc, asset_paths = copy_document_assets(
       doc=doc,
       output_dir=output_dir,
       generator=StaticSiteGenerator.HUGO,
       source_file=Path('document.md')
   )

   # Generate output filename
   filename = generate_output_filename(
       source=Path('document.md'),
       metadata=doc.metadata,
       generator=StaticSiteGenerator.HUGO
   )

   # Scaffold a site
   scaffolder = SiteScaffolder(StaticSiteGenerator.JEKYLL)
   scaffolder.scaffold(output_dir)

Module Documentation
~~~~~~~~~~~~~~~~~~~~

See the complete API reference:

- :py:mod:`all2md.utils.static_site` - Static site generation utilities
- :py:class:`all2md.utils.static_site.FrontmatterGenerator` - Frontmatter generation
- :py:class:`all2md.utils.static_site.SiteScaffolder` - Site scaffolding
- :py:class:`all2md.utils.static_site.ImageCollector` - Image collection
- :py:func:`all2md.utils.static_site.copy_document_assets` - Asset copying
- :py:func:`all2md.utils.static_site.generate_output_filename` - Filename generation

Comparison with HTML Templating
--------------------------------

all2md provides two distinct approaches for static site generation:

generate-site Command (This Document)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Best for:**

- Creating Hugo or Jekyll sites quickly
- Migrating documentation to static site generators
- Working with established static site ecosystems
- Batch converting document collections

**Features:**

- Purpose-built for Hugo/Jekyll
- Automatic frontmatter generation
- Site scaffolding
- Generator-specific conventions
- Integrated asset management

**Example:**

.. code-block:: bash

   all2md generate-site docs/ \
       --output-dir hugo-site \
       --generator hugo \
       --scaffold

HTML Renderer with Templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Best for:**

- Custom HTML generation with full control
- Creating standalone HTML sites
- Using custom templates (Jinja2, inject, replace modes)
- Integrating with custom build pipelines

**Features:**

- Full template control (Jinja2, inject, replace modes)
- CSS class mapping
- Syntax highlighting
- Table of contents generation
- Custom metadata integration

**Example:**

.. code-block:: bash

   all2md document.md --output-format html \
       --html-template-mode jinja \
       --html-template-file custom-template.html \
       --out document.html

For HTML templating documentation, see:

- :doc:`api/all2md.renderers.html` - HTML Renderer API
- :doc:`bidirectional` - Markdown to HTML conversion

Best Practices
--------------

Organizing Source Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use Meaningful Filenames:**

Source filenames become output filenames when there's no title metadata:

.. code-block:: text

   Good: getting-started-guide.md
   Poor: doc1.md

**Include Metadata:**

Add frontmatter to source markdown files for better results:

.. code-block:: markdown

   ---
   title: Advanced Python Techniques
   author: Sarah Developer
   date: 2025-01-22
   keywords: python, advanced, tutorial
   description: Learn advanced Python patterns
   ---

   # Advanced Python Techniques

   ...

**Organize Images Relative to Documents:**

Keep images near the documents that reference them:

.. code-block:: text

   docs/
   ├── guide.md
   ├── tutorial.md
   └── images/
       ├── guide-diagram.png
       └── tutorial-screenshot.png

Metadata Conventions
~~~~~~~~~~~~~~~~~~~~

**Use Consistent Date Formats:**

Prefer ISO 8601 format for dates:

.. code-block:: yaml

   date: 2025-01-22T14:30:00  # ISO 8601 with time
   date: 2025-01-22           # ISO 8601 date only

**Use Lists for Tags/Categories:**

Lists are more maintainable than comma-separated strings:

.. code-block:: yaml

   # Preferred
   tags:
     - python
     - tutorial
     - beginner

   # Also works
   tags: python, tutorial, beginner

**Include Descriptions:**

Descriptions improve SEO and readability:

.. code-block:: yaml

   description: A comprehensive guide to getting started with Python programming

Asset Organization
~~~~~~~~~~~~~~~~~~

**Use Relative Paths in Source:**

Relative paths work best with asset copying:

.. code-block:: markdown

   ![Diagram](./diagrams/architecture.png)    # Good
   ![Diagram](../images/arch.png)             # Good
   ![Diagram](/absolute/path/diagram.png)     # May not be found

**Avoid Special Characters in Filenames:**

Use simple, URL-safe filenames:

.. code-block:: text

   Good: user-flow-diagram.png
   Poor: User Flow (2024) [Final].png

**Don't Commit Remote URLs:**

Remote images won't be copied but will remain as references:

.. code-block:: markdown

   # These will be left as-is (not copied)
   ![Logo](https://example.com/logo.png)
   ![Avatar](http://cdn.example.com/avatar.jpg)

Testing Generated Sites
~~~~~~~~~~~~~~~~~~~~~~~

**Preview Locally:**

Always preview the generated site before deployment:

.. code-block:: bash

   # Hugo
   cd my-hugo-site
   hugo server -D  # -D includes drafts
   # Visit http://localhost:1313

   # Jekyll
   cd my-jekyll-blog
   bundle exec jekyll serve
   # Visit http://localhost:4000

**Check Asset Links:**

Verify that all images and assets load correctly in the preview.

**Review Frontmatter:**

Check that metadata was mapped correctly by viewing the generated markdown files.

**Test Search and Navigation:**

If using a theme with search or navigation, ensure it works with your content structure.

Incremental Updates
~~~~~~~~~~~~~~~~~~~

**Regenerate Only Changed Content:**

Use ``--exclude`` to skip already-converted files:

.. code-block:: bash

   # First run: convert everything
   all2md generate-site docs/ \
       --output-dir site \
       --generator hugo \
       --scaffold

   # Later: convert only new files
   all2md generate-site docs/new/ \
       --output-dir site \
       --generator hugo
   # Note: No --scaffold to avoid overwriting config

**Version Control:**

Commit both source documents and generated site to version control for reproducibility:

.. code-block:: text

   project/
   ├── source-docs/         # Original documents (commit)
   ├── hugo-site/           # Generated site (commit)
   └── .gitignore           # Ignore build artifacts

See Also
--------

**Related Documentation:**

- :doc:`cli` - Complete CLI reference with all global options
- :doc:`bidirectional` - Markdown to HTML and other formats
- :doc:`options` - Document conversion options
- :doc:`transforms` - Document transformation guide
- :doc:`attachments` - Attachment handling strategies

**API Reference:**

- :py:mod:`all2md.utils.static_site` - Static site generation utilities
- :py:class:`all2md.renderers.html.HtmlRenderer` - HTML renderer for custom templates

**External Resources:**

- `Hugo Documentation <https://gohugo.io/documentation/>`_ - Official Hugo docs
- `Jekyll Documentation <https://jekyllrb.com/docs/>`_ - Official Jekyll docs
- `Hugo Themes <https://themes.gohugo.io/>`_ - Hugo theme gallery
- `Jekyll Themes <https://jekyllthemes.io/>`_ - Jekyll theme gallery

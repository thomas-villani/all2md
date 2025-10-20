Static Site Generation
======================

all2md includes powerful HTML templating features that enable you to generate professional static websites from Markdown documents. Whether you're building a blog, documentation site, or marketing pages, the HTML renderer provides flexible template modes and customization options.

.. contents::
   :local:
   :depth: 2

Overview
--------

The HTML renderer supports three template modes plus CSS class mapping for maximum flexibility:

**Template Modes:**

- **inject**: Inject rendered HTML into existing HTML files at CSS selectors
- **replace**: Replace placeholder strings in template files with content
- **jinja**: Use Jinja2 template engine with rich context (content, metadata, TOC, headings, AST)

**Key Features:**

- ✓ Multiple template modes for different workflows
- ✓ CSS class mapping for custom styling
- ✓ Table of contents generation
- ✓ Metadata integration
- ✓ Security-first design (Jinja autoescape)
- ✓ Multi-document workflows

Quick Start
-----------

Basic Inject Mode
~~~~~~~~~~~~~~~~~

Inject your converted content into an existing HTML layout:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Create an HTML layout file
   with open('layout.html', 'w') as f:
       f.write('''<!DOCTYPE html>
   <html>
   <head><title>My Site</title></head>
   <body>
       <nav><!-- navigation --></nav>
       <main id="content">
           <!-- Content will be injected here -->
       </main>
       <footer>© 2025</footer>
   </body>
   </html>''')

   # Convert Markdown and inject into layout
   options = HtmlRendererOptions(
       template_mode='inject',
       template_file='layout.html',
       template_selector='#content',
       injection_mode='replace'
   )

   html = from_markdown('article.md', target_format='html', renderer_options=options)

   # Write the complete page
   with open('article.html', 'w') as f:
       f.write(html)

Basic Replace Mode
~~~~~~~~~~~~~~~~~~

Replace placeholders in a template file:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Create a template with placeholders
   with open('template.html', 'w') as f:
       f.write('''<!DOCTYPE html>
   <html>
   <head>
       <title>{TITLE}</title>
       <meta name="author" content="{AUTHOR}">
   </head>
   <body>
       <h1>{TITLE}</h1>
       <div class="content">{CONTENT}</div>
   </body>
   </html>''')

   # Convert with placeholder replacement
   options = HtmlRendererOptions(
       template_mode='replace',
       template_file='template.html'
   )

   # Markdown file with frontmatter
   markdown = '''---
   title: My Article
   author: Jane Doe
   ---

   # Introduction

   This is my article content.
   '''

   html = from_markdown(markdown, target_format='html', renderer_options=options)

Basic Jinja Mode
~~~~~~~~~~~~~~~~

Use full Jinja2 template engine with rich context:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Create a Jinja2 template
   with open('blog.html', 'w') as f:
       f.write('''<!DOCTYPE html>
   <html>
   <head>
       <title>{{ title }}</title>
   </head>
   <body>
       <article>
           <h1>{{ title }}</h1>
           <p class="meta">By {{ metadata.author }} | {{ metadata.date }}</p>

           {{ content }}

           {% if headings %}
           <aside>
               <h2>Table of Contents</h2>
               {{ toc_html }}
           </aside>
           {% endif %}
       </article>
   </body>
   </html>''')

   # Convert with Jinja2 template
   options = HtmlRendererOptions(
       template_mode='jinja',
       template_file='blog.html',
       include_toc=True
   )

   html = from_markdown('post.md', target_format='html', renderer_options=options)

CLI Usage
---------

All static site generation features are available through the ``all2md`` command-line interface. This section shows practical CLI examples for common static site workflows.

Basic HTML Conversion
~~~~~~~~~~~~~~~~~~~~~~

Convert Markdown to standalone HTML:

.. code-block:: bash

   # Convert single file to HTML
   all2md article.md --output-type html --out article.html

   # Convert with syntax highlighting disabled
   all2md post.md --output-type html --no-syntax-highlighting --out post.html

   # Generate HTML fragment (no <html>, <head>, <body> tags)
   all2md content.md --output-type html --no-standalone --out content-fragment.html

Using Inject Mode
~~~~~~~~~~~~~~~~~~

Inject converted content into an existing HTML layout at a CSS selector:

.. code-block:: bash

   # Inject into layout at #content selector (default)
   all2md article.md --output-type html \
       --html-template-mode inject \
       --html-template-file layout.html \
       --out article.html

   # Inject at custom selector
   all2md docs.md --output-type html \
       --html-template-mode inject \
       --html-template-file docs-layout.html \
       --html-template-selector "#main-content" \
       --out docs.html

   # Append content instead of replacing
   all2md update.md --output-type html \
       --html-template-mode inject \
       --html-template-file page.html \
       --html-template-selector "#updates" \
       --html-injection-mode append \
       --out page.html

Using Replace Mode
~~~~~~~~~~~~~~~~~~~

Replace placeholders in a template file:

.. code-block:: bash

   # Replace {CONTENT} placeholder in template
   all2md post.md --output-type html \
       --html-template-mode replace \
       --html-template-file blog-template.html \
       --out post.html

   # Use custom placeholder
   all2md article.md --output-type html \
       --html-template-mode replace \
       --html-template-file template.html \
       --html-content-placeholder "{{MAIN_CONTENT}}" \
       --out article.html

   # Include table of contents
   all2md guide.md --output-type html \
       --html-template-mode replace \
       --html-template-file template.html \
       --html-include-toc \
       --out guide.html

Using Jinja Mode
~~~~~~~~~~~~~~~~~

Use Jinja2 templates with full context (content, metadata, headings, TOC):

.. code-block:: bash

   # Basic Jinja template rendering
   all2md post.md --output-type html \
       --html-template-mode jinja \
       --html-template-file blog-post.html \
       --out post.html

   # With table of contents and syntax highlighting
   all2md tutorial.md --output-type html \
       --html-template-mode jinja \
       --html-template-file tutorial-template.html \
       --html-include-toc \
       --html-syntax-highlighting \
       --out tutorial.html

Batch Conversion
~~~~~~~~~~~~~~~~~

Convert multiple files at once for static site generation:

.. code-block:: bash

   # Convert all markdown files in a directory (with parallel processing)
   all2md posts/*.md --output-type html \
       --html-template-mode jinja \
       --html-template-file blog-post.html \
       --output-dir public/ \
       --parallel

   # Recursive conversion with template
   all2md docs/ --recursive --output-type html \
       --html-template-mode inject \
       --html-template-file docs-layout.html \
       --output-dir site/docs/ \
       --parallel

   # Convert with custom CSS classes (Tailwind)
   all2md content/*.md --output-type html \
       --html-template-mode jinja \
       --html-template-file page.html \
       --html-css-class-map '{"Heading": "text-2xl font-bold", "Paragraph": "mb-4"}' \
       --output-dir dist/ \
       --parallel

Complete CLI Example
~~~~~~~~~~~~~~~~~~~~~

Generate a complete blog site from markdown posts:

.. code-block:: bash

   #!/bin/bash
   # Generate blog site with consistent layout

   # Create output directory
   mkdir -p public

   # Convert all blog posts with Jinja template
   all2md posts/*.md \
       --output-type html \
       --html-template-mode jinja \
       --html-template-file templates/blog-post.html \
       --html-include-toc \
       --html-syntax-highlighting \
       --output-dir public/ \
       --parallel

   echo "Blog site generated in public/"

Template Modes
--------------

Inject Mode
~~~~~~~~~~~

Inject mode uses BeautifulSoup to inject your rendered content into an existing HTML document at a specified CSS selector. This is perfect for maintaining consistent site structure across multiple pages.

**Options:**

- ``template_selector``: CSS selector for injection target (default: ``#content``)
- ``injection_mode``: How to inject content (``append``, ``prepend``, or ``replace``)

**Example: Documentation Site**

.. code-block:: python

   from all2md import from_markdown, to_ast
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path

   # Create a documentation site layout
   layout = '''<!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <title>Documentation</title>
       <link rel="stylesheet" href="/css/docs.css">
   </head>
   <body>
       <div class="container">
           <aside class="sidebar">
               <nav>
                   <ul>
                       <li><a href="/docs/intro.html">Introduction</a></li>
                       <li><a href="/docs/guide.html">User Guide</a></li>
                       <li><a href="/docs/api.html">API Reference</a></li>
                   </ul>
               </nav>
           </aside>
           <main class="content" id="main-content">
               <!-- Documentation content injected here -->
           </main>
       </div>
       <footer>
           <p>Documentation v1.0 | <a href="/about">About</a></p>
       </footer>
   </body>
   </html>'''

   # Save layout
   Path('layout.html').write_text(layout)

   # Convert multiple documentation pages
   docs = [
       ('intro.md', 'intro.html'),
       ('guide.md', 'guide.html'),
       ('api.md', 'api.html')
   ]

   options = HtmlRendererOptions(
       template_mode='inject',
       template_file='layout.html',
       template_selector='#main-content',
       injection_mode='replace'
   )

   for md_file, html_file in docs:
       html = from_markdown(md_file, target_format='html', renderer_options=options)
       Path(html_file).write_text(html)

   print("Documentation site generated!")

**Injection Modes:**

- **replace**: Replace all content inside the target element (most common)
- **append**: Add content after existing content in the target element
- **prepend**: Add content before existing content in the target element

**Example: Append Mode**

.. code-block:: python

   # Useful for adding content to existing pages
   options = HtmlRendererOptions(
       template_mode='inject',
       template_file='existing_page.html',
       template_selector='#updates',
       injection_mode='append'  # Add to end of #updates section
   )

   html = from_markdown('new_update.md', target_format='html', renderer_options=options)

Replace Mode
~~~~~~~~~~~~

Replace mode performs simple string substitution on template files. It's fast, requires no additional dependencies, and is perfect for simple templates.

**Available Placeholders:**

- ``{CONTENT}``: Rendered HTML content (customizable via ``content_placeholder``)
- ``{TITLE}``: Document title from metadata
- ``{AUTHOR}``: Author from metadata
- ``{DATE}``: Date from metadata
- ``{DESCRIPTION}``: Description from metadata
- ``{TOC}``: Table of contents HTML (if ``include_toc=True``)

**Example: Blog Post Template**

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path

   # Create a blog post template
   template = '''<!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{TITLE} | My Blog</title>
       <meta name="author" content="{AUTHOR}">
       <meta name="description" content="{DESCRIPTION}">
       <style>
           body {
               max-width: 800px;
               margin: 0 auto;
               padding: 2rem;
               font-family: -apple-system, sans-serif;
               line-height: 1.6;
           }
           .meta { color: #666; margin-bottom: 2rem; }
           .toc { background: #f5f5f5; padding: 1rem; margin-bottom: 2rem; }
       </style>
   </head>
   <body>
       <article>
           <header>
               <h1>{TITLE}</h1>
               <div class="meta">
                   <span>By {AUTHOR}</span> |
                   <time>{DATE}</time>
               </div>
           </header>

           <div class="toc">
               {TOC}
           </div>

           <div class="content">
               {CONTENT}
           </div>
       </article>
       <footer>
           <p><a href="/">← Back to blog</a></p>
       </footer>
   </body>
   </html>'''

   # Save template
   Path('blog_template.html').write_text(template)

   # Convert blog post
   markdown = '''---
   title: Getting Started with Python
   author: John Developer
   date: 2025-01-15
   description: A beginner's guide to Python programming
   ---

   # Introduction

   Python is a versatile programming language.

   ## Installation

   First, install Python from python.org.

   ## Your First Program

   ```python
   print("Hello, World!")
   ```
   '''

   options = HtmlRendererOptions(
       template_mode='replace',
       template_file='blog_template.html',
       include_toc=True
   )

   html = from_markdown(markdown, target_format='html', renderer_options=options)
   Path('python-intro.html').write_text(html)

**Custom Content Placeholder:**

.. code-block:: python

   # Use a different placeholder for content
   template = '<html><body>{{MAIN_CONTENT}}</body></html>'

   options = HtmlRendererOptions(
       template_mode='replace',
       template_file='template.html',
       content_placeholder='{{MAIN_CONTENT}}'
   )

Jinja Mode
~~~~~~~~~~

Jinja mode provides the most powerful templating with full access to Jinja2 features including loops, conditionals, filters, and template inheritance.

**Template Context:**

The Jinja template receives a rich context with the following variables:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Variable
     - Description
   * - ``content``
     - Rendered HTML content (marked as safe)
   * - ``title``
     - Document title from metadata or 'Document'
   * - ``metadata``
     - Complete metadata dictionary
   * - ``headings``
     - List of heading dictionaries: ``[{'level': 1, 'id': 'heading-0', 'text': 'Introduction'}, ...]``
   * - ``toc_html``
     - Pre-rendered table of contents HTML (marked as safe)
   * - ``footnotes``
     - List of footnote dictionaries: ``[{'identifier': 'fn1'}, ...]``
   * - ``ast_json``
     - Complete document AST serialized to JSON

**Security Note:**

Jinja templates are configured with autoescape enabled for security. The ``content`` and ``toc_html`` are marked as safe since they're generated by the renderer.

**Example: Advanced Blog with Jinja**

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path

   # Create Jinja2 template with advanced features
   template = '''<!DOCTYPE html>
   <html lang="{{ metadata.get('language', 'en') }}">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{{ title }} | Tech Blog</title>

       {% if metadata.author %}
       <meta name="author" content="{{ metadata.author }}">
       {% endif %}

       {% if metadata.tags %}
       <meta name="keywords" content="{{ metadata.tags|join(', ') }}">
       {% endif %}

       <style>
           body {
               max-width: 800px;
               margin: 0 auto;
               padding: 2rem;
               font-family: system-ui, sans-serif;
           }
           .header {
               border-bottom: 2px solid #333;
               padding-bottom: 1rem;
               margin-bottom: 2rem;
           }
           .tags {
               display: flex;
               gap: 0.5rem;
               margin-top: 1rem;
           }
           .tag {
               background: #f0f0f0;
               padding: 0.25rem 0.75rem;
               border-radius: 1rem;
               font-size: 0.875rem;
           }
           .toc {
               background: #f9f9f9;
               border-left: 4px solid #333;
               padding: 1rem;
               margin: 2rem 0;
           }
           .reading-time {
               color: #666;
               font-size: 0.875rem;
           }
       </style>
   </head>
   <body>
       <article>
           <header class="header">
               <h1>{{ title }}</h1>

               <div class="meta">
                   {% if metadata.author %}
                   <span>By <strong>{{ metadata.author }}</strong></span>
                   {% endif %}

                   {% if metadata.date %}
                   <span> • {{ metadata.date }}</span>
                   {% endif %}

                   {% if metadata.reading_time %}
                   <span class="reading-time"> • {{ metadata.reading_time }} min read</span>
                   {% endif %}
               </div>

               {% if metadata.tags %}
               <div class="tags">
                   {% for tag in metadata.tags %}
                   <span class="tag">{{ tag }}</span>
                   {% endfor %}
               </div>
               {% endif %}
           </header>

           {% if headings and headings|length > 2 %}
           <aside class="toc">
               <h2>Table of Contents</h2>
               {{ toc_html }}
           </aside>
           {% endif %}

           <div class="content">
               {{ content }}
           </div>

           {% if footnotes %}
           <section class="footnotes">
               <h2>Footnotes</h2>
               <!-- Footnotes are auto-rendered in content -->
           </section>
           {% endif %}
       </article>

       <footer>
           <p>
               <a href="/">← Back to blog</a>
               {% if metadata.next_post %}
               | <a href="{{ metadata.next_post }}">Next post →</a>
               {% endif %}
           </p>
       </footer>
   </body>
   </html>'''

   Path('blog_jinja.html').write_text(template)

   # Create blog post with rich metadata
   markdown = '''---
   title: Advanced Python Tips
   author: Sarah Developer
   date: 2025-01-20
   tags: [python, programming, tips]
   reading_time: 5
   language: en
   next_post: /posts/python-best-practices.html
   ---

   # Introduction

   Learn advanced Python techniques.

   ## Tip 1: List Comprehensions

   Use list comprehensions for cleaner code.

   ## Tip 2: Context Managers

   Always use context managers for resources.
   '''

   options = HtmlRendererOptions(
       template_mode='jinja',
       template_file='blog_jinja.html',
       include_toc=True,
       syntax_highlighting=True
   )

   html = from_markdown(markdown, target_format='html', renderer_options=options)
   Path('python-tips.html').write_text(html)

**Using Jinja Loops:**

.. code-block:: jinja

   {% for heading in headings %}
       <p>Level {{ heading.level }}: {{ heading.text }}</p>
   {% endfor %}

**Using Jinja Conditionals:**

.. code-block:: jinja

   {% if metadata.featured %}
       <div class="featured-badge">Featured Post</div>
   {% endif %}

**Using Jinja Filters:**

.. code-block:: jinja

   <time>{{ metadata.date|upper }}</time>
   <p>Tags: {{ metadata.tags|join(' • ') }}</p>

CSS Class Mapping
-----------------

CSS class mapping allows you to add custom CSS classes to AST node types, enabling integration with CSS frameworks like Tailwind or custom styling systems.

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   options = HtmlRendererOptions(
       standalone=False,  # Just the content fragment
       css_class_map={
           'Heading': 'prose-heading',
           'Paragraph': 'prose-para',
           'CodeBlock': 'code-block',
           'Table': 'data-table',
           'BlockQuote': 'quote',
           'List': 'list-styled',
           'Link': 'link-primary',
           'Image': 'img-responsive'
       }
   )

   html = from_markdown('document.md', target_format='html', renderer_options=options)

Multiple Classes
~~~~~~~~~~~~~~~~

You can assign multiple classes to a single node type:

.. code-block:: python

   options = HtmlRendererOptions(
       css_class_map={
           'Heading': ['text-2xl', 'font-bold', 'mb-4'],
           'Paragraph': ['text-base', 'leading-relaxed', 'mb-4'],
           'CodeBlock': ['font-mono', 'text-sm', 'bg-gray-100', 'p-4']
       }
   )

Result:

.. code-block:: html

   <h1 class="text-2xl font-bold mb-4">My Heading</h1>
   <p class="text-base leading-relaxed mb-4">Paragraph content</p>
   <pre class="font-mono text-sm bg-gray-100 p-4"><code>...</code></pre>

Tailwind CSS Integration
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path

   # Tailwind-styled classes
   tailwind_classes = {
       'Heading': 'text-3xl font-bold text-gray-900 mt-8 mb-4',
       'Paragraph': 'text-gray-700 leading-relaxed mb-4',
       'CodeBlock': 'bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto',
       'BlockQuote': 'border-l-4 border-blue-500 pl-4 italic text-gray-600',
       'Table': 'min-w-full divide-y divide-gray-200',
       'Link': 'text-blue-600 hover:text-blue-800 underline',
       'Image': 'max-w-full h-auto rounded-lg shadow-lg',
       'List': 'list-disc list-inside space-y-2',
       'ThematicBreak': 'my-8 border-t-2 border-gray-300'
   }

   # Create HTML with Tailwind CSS
   template = '''<!DOCTYPE html>
   <html>
   <head>
       <title>{TITLE}</title>
       <script src="https://cdn.tailwindcss.com"></script>
   </head>
   <body class="bg-white">
       <div class="max-w-4xl mx-auto px-4 py-8">
           {CONTENT}
       </div>
   </body>
   </html>'''

   Path('tailwind_template.html').write_text(template)

   options = HtmlRendererOptions(
       template_mode='replace',
       template_file='tailwind_template.html',
       css_class_map=tailwind_classes,
       syntax_highlighting=True
   )

   html = from_markdown('article.md', target_format='html', renderer_options=options)

Supported Node Types
~~~~~~~~~~~~~~~~~~~~

You can customize CSS classes for these AST node types:

- ``Heading`` - All heading levels (h1-h6)
- ``Paragraph`` - Paragraph elements
- ``CodeBlock`` - Code blocks (merges with language class)
- ``BlockQuote`` - Blockquote elements
- ``List`` - List containers (ul/ol)
- ``ListItem`` - Individual list items
- ``Table`` - Table elements
- ``Link`` - Anchor elements
- ``Image`` - Image elements
- ``ThematicBreak`` - Horizontal rules
- ``DefinitionList`` - Definition list (dl)
- ``DefinitionTerm`` - Definition term (dt)
- ``DefinitionDescription`` - Definition description (dd)

**Note:** For code blocks, custom classes are merged with the language class:

.. code-block:: python

   css_class_map={'CodeBlock': 'custom-code'}

   # Results in:
   # <pre><code class="language-python custom-code">...</code></pre>

Real-World Examples
-------------------

Blog Generation
~~~~~~~~~~~~~~~

Complete blog system with index page and individual posts:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path
   import json

   class BlogGenerator:
       """Generate a complete blog from Markdown posts."""

       def __init__(self, posts_dir: str, output_dir: str):
           self.posts_dir = Path(posts_dir)
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(exist_ok=True)

           # Create post template
           self.post_template = '''<!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <title>{{ title }} | My Blog</title>
       <meta name="author" content="{{ metadata.author }}">
       <link rel="stylesheet" href="/css/style.css">
   </head>
   <body>
       <header class="site-header">
           <h1><a href="/">My Blog</a></h1>
           <nav>
               <a href="/about.html">About</a>
               <a href="/archive.html">Archive</a>
           </nav>
       </header>

       <main class="post">
           <article>
               <header class="post-header">
                   <h1>{{ title }}</h1>
                   <div class="post-meta">
                       <span class="author">{{ metadata.author }}</span>
                       <time datetime="{{ metadata.date }}">{{ metadata.date }}</time>
                   </div>
               </header>

               {{ content }}
           </article>
       </main>

       <footer>
           <p>© 2025 My Blog</p>
       </footer>
   </body>
   </html>'''

           Path('post_template.html').write_text(self.post_template)

       def generate_post(self, md_file: Path) -> dict:
           """Generate HTML for a single post."""
           options = HtmlRendererOptions(
               template_mode='jinja',
               template_file='post_template.html',
               syntax_highlighting=True
           )

           html = from_markdown(str(md_file), target_format='html', renderer_options=options)

           # Extract metadata for index
           from all2md import to_ast
           doc = to_ast(str(md_file))

           slug = md_file.stem
           output_file = self.output_dir / f"{slug}.html"
           output_file.write_text(html)

           return {
               'slug': slug,
               'url': f"/{slug}.html",
               'title': doc.metadata.get('title', slug),
               'author': doc.metadata.get('author', 'Unknown'),
               'date': doc.metadata.get('date', ''),
               'excerpt': doc.metadata.get('excerpt', '')
           }

       def generate_index(self, posts: list):
           """Generate blog index page."""
           index_html = '''<!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <title>My Blog</title>
       <link rel="stylesheet" href="/css/style.css">
   </head>
   <body>
       <header class="site-header">
           <h1>My Blog</h1>
       </header>

       <main class="post-list">'''

           for post in sorted(posts, key=lambda p: p['date'], reverse=True):
               index_html += f'''
           <article class="post-preview">
               <h2><a href="{post['url']}">{post['title']}</a></h2>
               <div class="post-meta">
                   <span>{post['author']}</span> •
                   <time>{post['date']}</time>
               </div>
               <p>{post['excerpt']}</p>
           </article>'''

           index_html += '''
       </main>

       <footer>
           <p>© 2025 My Blog</p>
       </footer>
   </body>
   </html>'''

           (self.output_dir / 'index.html').write_text(index_html)

       def generate(self):
           """Generate complete blog."""
           posts = []

           for md_file in self.posts_dir.glob('*.md'):
               print(f"Generating: {md_file.name}")
               post_info = self.generate_post(md_file)
               posts.append(post_info)

           self.generate_index(posts)

           print(f"\nGenerated {len(posts)} posts")
           print(f"Output: {self.output_dir}/index.html")

   # Usage
   blog = BlogGenerator(posts_dir='./posts', output_dir='./public')
   blog.generate()

Documentation Sites
~~~~~~~~~~~~~~~~~~~

Multi-page documentation with navigation:

.. code-block:: python

   from all2md import from_markdown, to_ast
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path

   class DocGenerator:
       """Generate documentation site."""

       def __init__(self, docs_dir: str, output_dir: str):
           self.docs_dir = Path(docs_dir)
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(exist_ok=True)

       def build_navigation(self, docs: list) -> str:
           """Build navigation HTML."""
           nav_html = '<nav class="docs-nav"><ul>'

           for doc in docs:
               nav_html += f'<li><a href="/{doc["slug"]}.html">{doc["title"]}</a></li>'

           nav_html += '</ul></nav>'
           return nav_html

       def generate(self):
           """Generate documentation site."""
           # Discover all docs
           docs = []
           for md_file in sorted(self.docs_dir.glob('*.md')):
               doc_ast = to_ast(str(md_file))
               docs.append({
                   'slug': md_file.stem,
                   'title': doc_ast.metadata.get('title', md_file.stem),
                   'path': md_file
               })

           # Generate navigation
           nav_html = self.build_navigation(docs)

           # Create layout with navigation
           layout = f'''<!DOCTYPE html>
   <html>
   <head>
       <meta charset="UTF-8">
       <title>Documentation</title>
       <link rel="stylesheet" href="/css/docs.css">
   </head>
   <body>
       <div class="docs-container">
           {nav_html}
           <main id="content"></main>
       </div>
   </body>
   </html>'''

           Path('docs_layout.html').write_text(layout)

           # Generate each page
           options = HtmlRendererOptions(
               template_mode='inject',
               template_file='docs_layout.html',
               template_selector='#content',
               injection_mode='replace',
               include_toc=True
           )

           for doc in docs:
               html = from_markdown(
                   str(doc['path']),
                   target_format='html',
                   renderer_options=options
               )

               output_file = self.output_dir / f"{doc['slug']}.html"
               output_file.write_text(html)
               print(f"Generated: {output_file}")

   # Usage
   docs = DocGenerator(docs_dir='./docs', output_dir='./site')
   docs.generate()

Marketing Pages
~~~~~~~~~~~~~~~

Landing page with custom styling:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Marketing page with hero section
   template = '''<!DOCTYPE html>
   <html>
   <head>
       <title>{{ metadata.product_name }}</title>
       <style>
           .hero {
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               color: white;
               padding: 4rem 2rem;
               text-align: center;
           }
           .cta-button {
               background: white;
               color: #667eea;
               padding: 1rem 2rem;
               border-radius: 2rem;
               text-decoration: none;
               font-weight: bold;
           }
       </style>
   </head>
   <body>
       <div class="hero">
           <h1>{{ metadata.product_name }}</h1>
           <p class="tagline">{{ metadata.tagline }}</p>
           <a href="{{ metadata.cta_link }}" class="cta-button">
               {{ metadata.cta_text }}
           </a>
       </div>

       <div class="content">
           {{ content }}
       </div>
   </body>
   </html>'''

   markdown = '''---
   product_name: Amazing Product
   tagline: The best solution for your needs
   cta_link: /signup
   cta_text: Get Started Free
   ---

   # Features

   ## Fast & Reliable

   Our product is built for speed.

   ## Secure by Default

   Security is our top priority.
   '''

   options = HtmlRendererOptions(
       template_mode='jinja',
       template_file='landing.html'
   )

   html = from_markdown(markdown, target_format='html', renderer_options=options)

Advanced Features
-----------------

Table of Contents Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable automatic TOC generation from document headings:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   options = HtmlRendererOptions(
       template_mode='replace',
       template_file='template.html',
       include_toc=True  # Enable TOC generation
   )

   # In template.html, use {TOC} placeholder
   # In Jinja templates, use {{ toc_html }}

The generated TOC:

.. code-block:: html

   <ul>
     <li><a href="#heading-0">Introduction</a></li>
     <li><a href="#heading-1">Chapter 1</a></li>
     <li><a href="#heading-2">Chapter 2</a></li>
   </ul>

Metadata Integration
~~~~~~~~~~~~~~~~~~~~

Access metadata in templates:

**Replace Mode:**

.. code-block:: html

   <title>{TITLE}</title>
   <meta name="author" content="{AUTHOR}">
   <meta name="description" content="{DESCRIPTION}">

**Jinja Mode:**

.. code-block:: jinja

   <title>{{ metadata.title }}</title>
   <meta name="author" content="{{ metadata.author }}">

   {% if metadata.custom_field %}
   <div>{{ metadata.custom_field }}</div>
   {% endif %}

Heading Extraction
~~~~~~~~~~~~~~~~~~

In Jinja templates, access heading information:

.. code-block:: jinja

   <nav>
       <h2>On This Page</h2>
       <ul>
       {% for heading in headings %}
           <li class="level-{{ heading.level }}">
               <a href="#{{ heading.id }}">{{ heading.text }}</a>
           </li>
       {% endfor %}
       </ul>
   </nav>

AST Access
~~~~~~~~~~

Jinja templates have access to the complete AST as JSON:

.. code-block:: jinja

   {% if ast_json %}
   <script>
       const documentAST = {{ ast_json | safe }};
       // Use AST for custom processing
   </script>
   {% endif %}

Best Practices
--------------

Template Organization
~~~~~~~~~~~~~~~~~~~~~

Organize templates for maintainability:

.. code-block:: text

   project/
   ├── templates/
   │   ├── base.html          # Base template
   │   ├── blog_post.html     # Blog post template
   │   ├── docs_page.html     # Documentation template
   │   └── landing.html       # Landing page template
   ├── content/
   │   ├── posts/
   │   │   ├── post1.md
   │   │   └── post2.md
   │   └── docs/
   │       ├── intro.md
   │       └── guide.md
   └── output/
       └── # Generated HTML

**Template Reuse:**

.. code-block:: python

   # Create template variants
   templates = {
       'blog': 'templates/blog_post.html',
       'docs': 'templates/docs_page.html',
       'landing': 'templates/landing.html'
   }

   def render_with_template(md_file: str, template_type: str):
       options = HtmlRendererOptions(
           template_mode='jinja',
           template_file=templates[template_type]
       )
       return from_markdown(md_file, target_format='html', renderer_options=options)

Security Considerations
~~~~~~~~~~~~~~~~~~~~~~~

**Jinja2 Autoescape:**

The renderer automatically configures Jinja2 with autoescape enabled for HTML and XML. This protects against XSS attacks from user-provided metadata.

.. code-block:: python

   # Autoescape is enabled automatically
   options = HtmlRendererOptions(
       template_mode='jinja',
       template_file='template.html'
   )
   # User input in metadata is automatically escaped

**Trusted Content:**

The ``content`` and ``toc_html`` variables are marked as safe because they're generated by the renderer itself:

.. code-block:: jinja

   {{ content }}      {# Safe HTML from renderer #}
   {{ toc_html }}     {# Safe HTML from renderer #}
   {{ metadata.user_input }}  {# Escaped for safety #}

**File Validation:**

Always validate template file paths:

.. code-block:: python

   from pathlib import Path

   def safe_render(md_file: str, template_file: str):
       """Safely render with validated template."""
       template_path = Path(template_file).resolve()

       # Ensure template is in allowed directory
       allowed_dir = Path('./templates').resolve()
       if not str(template_path).startswith(str(allowed_dir)):
           raise ValueError("Template must be in templates directory")

       if not template_path.exists():
           raise FileNotFoundError(f"Template not found: {template_file}")

       options = HtmlRendererOptions(
           template_mode='jinja',
           template_file=str(template_path)
       )

       return from_markdown(md_file, target_format='html', renderer_options=options)

Performance Tips
~~~~~~~~~~~~~~~~

**Cache Rendered Content:**

.. code-block:: python

   from functools import lru_cache

   @lru_cache(maxsize=100)
   def render_cached(md_file: str, template: str) -> str:
       """Cache rendered HTML for repeated access."""
       options = HtmlRendererOptions(
           template_mode='jinja',
           template_file=template
       )
       return from_markdown(md_file, target_format='html', renderer_options=options)

**Batch Processing:**

.. code-block:: python

   from concurrent.futures import ThreadPoolExecutor

   def batch_render(md_files: list, template: str) -> list:
       """Render multiple files in parallel."""
       options = HtmlRendererOptions(
           template_mode='jinja',
           template_file=template
       )

       def render_one(md_file):
           return from_markdown(md_file, target_format='html', renderer_options=options)

       with ThreadPoolExecutor(max_workers=4) as executor:
           return list(executor.map(render_one, md_files))

**Template Reuse:**

Create renderer once and reuse options:

.. code-block:: python

   # Good: Reuse options
   options = HtmlRendererOptions(
       template_mode='jinja',
       template_file='template.html'
   )

   for md_file in md_files:
       html = from_markdown(md_file, target_format='html', renderer_options=options)

Template Reusability
~~~~~~~~~~~~~~~~~~~~

Use consistent patterns across templates:

.. code-block:: jinja

   {# Base template pattern #}
   <!DOCTYPE html>
   <html lang="{{ metadata.get('language', 'en') }}">
   <head>
       <meta charset="UTF-8">
       <title>{{ title }}</title>
       {% block head %}{% endblock %}
   </head>
   <body>
       <header>{% block header %}{% endblock %}</header>
       <main>{{ content }}</main>
       <footer>{% block footer %}{% endblock %}</footer>
   </body>
   </html>

Bash Script Example
--------------------

This section demonstrates a complete static site generation workflow using bash scripts and the ``all2md`` CLI. The example shows how to convert multiple blog posts and automatically generate an index page.

Blog Post Template
~~~~~~~~~~~~~~~~~~~

First, create a Jinja2 template for blog posts (``templates/blog-post.html``):

.. code-block:: html

   <!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{{ title }} | My Blog</title>
       <meta name="author" content="{{ metadata.author }}">
       <meta name="description" content="{{ metadata.description }}">
       <style>
           body {
               max-width: 800px;
               margin: 0 auto;
               padding: 2rem;
               font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               line-height: 1.6;
               color: #333;
           }
           header {
               border-bottom: 2px solid #333;
               padding-bottom: 1rem;
               margin-bottom: 2rem;
           }
           .site-title {
               font-size: 1.5rem;
               font-weight: bold;
               text-decoration: none;
               color: #333;
           }
           nav a {
               margin-left: 1rem;
               color: #666;
               text-decoration: none;
           }
           nav a:hover {
               color: #333;
           }
           .post-meta {
               color: #666;
               font-size: 0.9rem;
               margin-bottom: 2rem;
           }
           .toc {
               background: #f5f5f5;
               padding: 1rem;
               margin: 2rem 0;
               border-left: 4px solid #333;
           }
           footer {
               margin-top: 3rem;
               padding-top: 1rem;
               border-top: 1px solid #ddd;
               color: #666;
               font-size: 0.9rem;
           }
       </style>
   </head>
   <body>
       <header>
           <a href="/index.html" class="site-title">My Blog</a>
           <nav>
               <a href="/index.html">Home</a>
               <a href="/about.html">About</a>
           </nav>
       </header>

       <article>
           <h1>{{ title }}</h1>
           <div class="post-meta">
               By {{ metadata.author }} on {{ metadata.date }}
           </div>

           {% if headings and headings|length > 2 %}
           <aside class="toc">
               <h2>Table of Contents</h2>
               {{ toc_html }}
           </aside>
           {% endif %}

           {{ content }}
       </article>

       <footer>
           <p><a href="/index.html">← Back to all posts</a></p>
       </footer>
   </body>
   </html>

Site Generation Script
~~~~~~~~~~~~~~~~~~~~~~~

Create a bash script (``generate-site.sh``) to convert posts and build the index page:

.. code-block:: bash

   #!/bin/bash
   # Generate static blog site from Markdown posts
   # Usage: ./generate-site.sh

   set -e  # Exit on error

   # Configuration
   POSTS_DIR="posts"
   OUTPUT_DIR="public"
   TEMPLATE_FILE="templates/blog-post.html"

   # Colors for output
   GREEN='\033[0;32m'
   BLUE='\033[0;34m'
   NC='\033[0m' # No Color

   echo -e "${BLUE}Starting blog generation...${NC}"

   # Convert all markdown posts to HTML in one batch command
   echo -e "${BLUE}Converting posts...${NC}"
   all2md "$POSTS_DIR"/*.md \
       --output-type html \
       --html-template-mode jinja \
       --html-template-file "$TEMPLATE_FILE" \
       --html-include-toc \
       --html-syntax-highlighting \
       --output-dir "$OUTPUT_DIR" \
       --parallel

   echo -e "${GREEN}Posts converted${NC}"

   # Generate index page
   echo -e "${BLUE}Generating index page...${NC}"

   # Create index.html with list of all posts
   cat > "$OUTPUT_DIR/index.html" << 'EOF'
   <!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>My Blog</title>
       <style>
           body {
               max-width: 800px;
               margin: 0 auto;
               padding: 2rem;
               font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               line-height: 1.6;
               color: #333;
           }
           header {
               border-bottom: 2px solid #333;
               padding-bottom: 1rem;
               margin-bottom: 2rem;
           }
           .site-title {
               font-size: 2rem;
               font-weight: bold;
               margin-bottom: 0.5rem;
           }
           nav a {
               margin-right: 1rem;
               color: #666;
               text-decoration: none;
           }
           nav a:hover {
               color: #333;
           }
           .post-list {
               list-style: none;
               padding: 0;
           }
           .post-item {
               margin-bottom: 2rem;
               padding-bottom: 2rem;
               border-bottom: 1px solid #eee;
           }
           .post-item:last-child {
               border-bottom: none;
           }
           .post-title {
               font-size: 1.5rem;
               margin-bottom: 0.5rem;
           }
           .post-title a {
               color: #333;
               text-decoration: none;
           }
           .post-title a:hover {
               color: #0066cc;
           }
           .post-meta {
               color: #666;
               font-size: 0.9rem;
               margin-bottom: 0.5rem;
           }
           .post-excerpt {
               color: #555;
           }
           footer {
               margin-top: 3rem;
               padding-top: 1rem;
               border-top: 1px solid #ddd;
               color: #666;
               font-size: 0.9rem;
               text-align: center;
           }
       </style>
   </head>
   <body>
       <header>
           <div class="site-title">My Blog</div>
           <nav>
               <a href="/index.html">Home</a>
               <a href="/about.html">About</a>
           </nav>
       </header>

       <main>
           <h1>Recent Posts</h1>
           <ul class="post-list">
   EOF

   # Extract metadata and add post entries
   for md_file in "$POSTS_DIR"/*.md; do
       if [ -f "$md_file" ]; then
           basename=$(basename "$md_file" .md)

           # Extract title from frontmatter (first line after ---)
           title=$(sed -n '/^---$/,/^---$/p' "$md_file" | grep '^title:' | sed 's/^title: *//')
           if [ -z "$title" ]; then
               title="$basename"
           fi

           # Extract author
           author=$(sed -n '/^---$/,/^---$/p' "$md_file" | grep '^author:' | sed 's/^author: *//')
           if [ -z "$author" ]; then
               author="Unknown"
           fi

           # Extract date
           date=$(sed -n '/^---$/,/^---$/p' "$md_file" | grep '^date:' | sed 's/^date: *//')
           if [ -z "$date" ]; then
               date="No date"
           fi

           # Extract description/excerpt
           description=$(sed -n '/^---$/,/^---$/p' "$md_file" | grep '^description:' | sed 's/^description: *//')
           if [ -z "$description" ]; then
               description=""
           fi

           # Add post entry to index
           cat >> "$OUTPUT_DIR/index.html" << ENTRY
               <li class="post-item">
                   <h2 class="post-title"><a href="${basename}.html">${title}</a></h2>
                   <div class="post-meta">By ${author} on ${date}</div>
                   <p class="post-excerpt">${description}</p>
               </li>
   ENTRY
       fi
   done

   # Close HTML
   cat >> "$OUTPUT_DIR/index.html" << 'EOF'
           </ul>
       </main>

       <footer>
           <p>&copy; 2025 My Blog. All rights reserved.</p>
       </footer>
   </body>
   </html>
   EOF

   echo -e "${GREEN}Index page generated${NC}"
   echo -e "${GREEN}Site generation complete!${NC}"
   echo -e "Output directory: ${BLUE}$OUTPUT_DIR${NC}"

Example Markdown Post
~~~~~~~~~~~~~~~~~~~~~

Create blog posts with frontmatter metadata (``posts/welcome.md``):

.. code-block:: markdown

   ---
   title: Welcome to My Blog
   author: Jane Doe
   date: 2025-01-15
   description: Introduction to my new blog and what you can expect to read here.
   ---

   # Welcome!

   This is my first blog post. I'm excited to share my thoughts on technology,
   programming, and life.

   ## What to Expect

   I'll be writing about:

   - Python programming tips
   - Web development tutorials
   - Book reviews
   - Travel adventures

   ## Getting Started

   Check out my [about page](/about.html) to learn more about me.

   Stay tuned for more posts!

Running the Script
~~~~~~~~~~~~~~~~~~

Make the script executable and run it:

.. code-block:: bash

   chmod +x generate-site.sh
   ./generate-site.sh

This will:

1. Convert all ``.md`` files in ``posts/`` to HTML using the Jinja template
2. Extract metadata (title, author, date, description) from each post's frontmatter
3. Generate ``index.html`` with a list of all posts and their metadata
4. Output everything to the ``public/`` directory

The resulting site structure:

.. code-block:: text

   public/
   ├── index.html          # Homepage with post list
   ├── welcome.html        # Individual post page
   ├── second-post.html    # Another post
   └── ...

Customization
~~~~~~~~~~~~~

Extend the script for additional features:

**Sort posts by date:**

.. code-block:: bash

   # Add before the post loop
   posts_with_dates=()
   for md_file in "$POSTS_DIR"/*.md; do
       date=$(sed -n '/^---$/,/^---$/p' "$md_file" | grep '^date:' | sed 's/^date: *//')
       posts_with_dates+=("$date|$md_file")
   done

   # Sort by date (newest first)
   IFS=$'\n' sorted=($(sort -r <<<"${posts_with_dates[*]}"))
   unset IFS

**Add RSS feed generation:**

.. code-block:: bash

   # Generate RSS feed
   cat > "$OUTPUT_DIR/feed.xml" << EOF
   <?xml version="1.0" encoding="UTF-8"?>
   <rss version="2.0">
       <channel>
           <title>My Blog</title>
           <link>https://myblog.com</link>
           <description>My personal blog</description>
   EOF

   # Add items from posts
   # ... (extract metadata and generate RSS items)

**Add sitemap.xml:**

.. code-block:: bash

   echo '<?xml version="1.0" encoding="UTF-8"?>' > "$OUTPUT_DIR/sitemap.xml"
   echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' >> "$OUTPUT_DIR/sitemap.xml"

   for html_file in "$OUTPUT_DIR"/*.html; do
       basename=$(basename "$html_file")
       echo "  <url><loc>https://myblog.com/$basename</loc></url>" >> "$OUTPUT_DIR/sitemap.xml"
   done

   echo '</urlset>' >> "$OUTPUT_DIR/sitemap.xml"

Complete Working Examples
--------------------------

Personal Blog System
~~~~~~~~~~~~~~~~~~~~

Complete example with multiple templates and workflows:

.. code-block:: python

   from all2md import from_markdown, to_ast
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path
   from datetime import datetime

   class PersonalBlog:
       """Complete personal blog generator."""

       def __init__(self):
           self.posts_dir = Path('posts')
           self.output_dir = Path('public')
           self.templates_dir = Path('templates')

           # Create directories
           for d in [self.posts_dir, self.output_dir, self.templates_dir]:
               d.mkdir(exist_ok=True)

           self.create_templates()

       def create_templates(self):
           """Create blog templates."""
           # Post template
           post_template = '''<!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <title>{{ title }} | Personal Blog</title>
       <meta name="author" content="{{ metadata.author }}">
       <link rel="stylesheet" href="/css/style.css">
   </head>
   <body>
       <header class="site-header">
           <h1><a href="/">Personal Blog</a></h1>
           <nav>
               <a href="/about.html">About</a>
               <a href="/archive.html">Archive</a>
           </nav>
       </header>

       <main>
           <article class="post">
               <header class="post-header">
                   <h1>{{ title }}</h1>
                   <div class="post-meta">
                       By {{ metadata.author }} on {{ metadata.date }}
                   </div>
               </header>

               {% if headings|length > 3 %}
               <aside class="toc">
                   <h2>Contents</h2>
                   {{ toc_html }}
               </aside>
               {% endif %}

               <div class="post-content">
                   {{ content }}
               </div>
           </article>
       </main>

       <footer>
           <p>© {{ year }} Personal Blog</p>
       </footer>
   </body>
   </html>'''

           (self.templates_dir / 'post.html').write_text(post_template)

       def render_post(self, md_file: Path) -> dict:
           """Render a blog post."""
           options = HtmlRendererOptions(
               template_mode='jinja',
               template_file=str(self.templates_dir / 'post.html'),
               include_toc=True,
               syntax_highlighting=True,
               css_class_map={
                   'CodeBlock': 'highlight',
                   'BlockQuote': 'quote',
                   'Image': 'post-image'
               }
           )

           # Parse for metadata
           doc = to_ast(str(md_file))

           # Add current year to metadata
           doc.metadata['year'] = datetime.now().year

           # Render
           html = from_markdown(str(md_file), target_format='html', renderer_options=options)

           # Save
           slug = md_file.stem
           output_file = self.output_dir / f"{slug}.html"
           output_file.write_text(html)

           return {
               'slug': slug,
               'title': doc.metadata.get('title', slug),
               'date': doc.metadata.get('date', ''),
               'author': doc.metadata.get('author', 'Unknown')
           }

       def generate(self):
           """Generate complete blog."""
           posts = []

           for md_file in self.posts_dir.glob('*.md'):
               post_info = self.render_post(md_file)
               posts.append(post_info)
               print(f"✓ Generated {post_info['slug']}")

           print(f"\nGenerated {len(posts)} posts to {self.output_dir}")

   # Usage
   blog = PersonalBlog()
   blog.generate()

Documentation Generator
~~~~~~~~~~~~~~~~~~~~~~~

Complete documentation site with search and navigation:

.. code-block:: python

   from all2md import from_markdown, to_ast
   from all2md.renderers.html import HtmlRendererOptions
   from pathlib import Path
   import json

   class DocsGenerator:
       """Generate documentation site."""

       def __init__(self, source_dir: str, output_dir: str):
           self.source_dir = Path(source_dir)
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(exist_ok=True)

       def build_search_index(self, docs: list) -> str:
           """Build search index JSON."""
           index = []
           for doc in docs:
               ast = to_ast(str(doc['source']))
               index.append({
                   'slug': doc['slug'],
                   'title': doc['title'],
                   'url': f"/{doc['slug']}.html"
               })

           return json.dumps(index, indent=2)

       def generate(self):
           """Generate documentation site."""
           # Discover docs
           docs = []
           for md_file in sorted(self.source_dir.rglob('*.md')):
               doc = to_ast(str(md_file))
               docs.append({
                   'slug': md_file.stem,
                   'title': doc.metadata.get('title', md_file.stem),
                   'source': md_file
               })

           # Build navigation
           nav_html = '<ul>' + ''.join(
               f'<li><a href="/{d["slug"]}.html">{d["title"]}</a></li>'
               for d in docs
           ) + '</ul>'

           # Create layout
           layout = f'''<!DOCTYPE html>
   <html>
   <head>
       <meta charset="UTF-8">
       <title>Documentation</title>
   </head>
   <body>
       <aside class="sidebar">
           <nav>{nav_html}</nav>
       </aside>
       <main id="content"></main>
   </body>
   </html>'''

           Path('docs_layout.html').write_text(layout)

           # Render each page
           options = HtmlRendererOptions(
               template_mode='inject',
               template_file='docs_layout.html',
               template_selector='#content',
               include_toc=True
           )

           for doc in docs:
               html = from_markdown(
                   str(doc['source']),
                   target_format='html',
                   renderer_options=options
               )
               (self.output_dir / f"{doc['slug']}.html").write_text(html)

           # Build search index
           search_index = self.build_search_index(docs)
           (self.output_dir / 'search-index.json').write_text(search_index)

   # Usage
   generator = DocsGenerator(source_dir='./docs', output_dir='./site')
   generator.generate()


See Also
--------

* :py:class:~all2md.renderers.html.HtmlRendererOptions
* :doc:`api/all2md.renderers.html` - Html Renderer
* :doc:`bidirectional` - Markdown to HTML conversion basics
* :doc:`options` - Complete options reference
* :doc:`recipes` - More real-world examples
* :doc:`integrations` - Framework integration examples
* :doc:`security` - Security best practices

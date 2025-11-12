Security
========

all2md includes comprehensive security features to protect against common vulnerabilities when processing documents, especially from untrusted sources. This guide covers the security model, network and filesystem controls, archive validation, and best practices for secure document conversion.

.. contents::
   :local:
   :depth: 2

Security Model Overview
-----------------------

The all2md threat model assumes every input could be hostile. The converter is designed to:

* Treat uploaded or scraped documents as **untrusted** while keeping parsing and rendering code **trusted**
* Default to least-privilege access for the network, filesystem, and process resources
* Fail securely when validation checks cannot be completed
* Provide layered defenses so a misconfiguration in one area does not expose the entire pipeline

For a deeper threat-model walk-through and architectural context, see :doc:`threat_model`.

Secure by Default
-----------------

.. important::

   all2md follows a ``secure by default`` philosophy:

   - Remote fetching is DISABLED by default
   - robots.txt is ENFORCED by default (strict mode)
   - Local file access is DISABLED by default
   - HTML is ESCAPED by default
   - OCR is DISABLED by default
   - Dangerous URL schemes are BLOCKED
   - Private IP ranges are BLOCKED

   Users must explicitly opt-in to potentially risky features.

.. code-block:: text
   :caption: Defense-in-depth layers

           ┌─────────────────────────────┐
           │  CLI presets & env guards   │  -- opt-in switches (``--safe-mode``, ``ALL2MD_DISABLE_NETWORK``)
           └──────────────┬──────────────┘
                          │
           ┌──────────────▼──────────────┐
           │ Parser options & validators │  -- ``NetworkFetchOptions``, ``LocalFileAccessOptions``
           └──────────────┬──────────────┘
                          │
           ┌──────────────▼──────────────┐
           │   Runtime policy checks     │  -- private IP blocking, SSRF filters, archive inspection
           └──────────────┬──────────────┘
                          │
           ┌──────────────▼──────────────┐
           │      Sanitized output       │  -- HTML escaping, attachment policies, metadata limits
           └─────────────────────────────┘

Key Risk Areas
--------------

When processing documents from untrusted sources, several security risks must be addressed:

* **Server-Side Request Forgery (SSRF)**: Malicious documents may reference internal network resources
* **Local File Access**: Documents may attempt to access sensitive local files via ``file://`` URLs
* **Resource Exhaustion**: Large or malicious files can consume excessive memory or processing time
* **Archive Bombs**: Compressed files may expand to consume disk space or memory

all2md provides defense mechanisms for all these scenarios through configurable security options and built-in protections.

Network Security (SSRF Protection)
----------------------------------

Understanding SSRF Risks
~~~~~~~~~~~~~~~~~~~~~~~~

Server-Side Request Forgery occurs when a document converter fetches remote resources (like images in HTML or PDF files) without proper validation. Attackers can exploit this to:

* Scan internal networks and services
* Access cloud metadata endpoints (AWS, Azure, GCP)
* Exfiltrate data to external servers
* Bypass firewall restrictions

Default stance
~~~~~~~~~~~~~~

Remote fetching is **disabled** unless explicitly enabled. The defaults in ``all2md.constants`` set ``DEFAULT_ALLOW_REMOTE_FETCH = False`` and ``DEFAULT_REQUIRE_HTTPS = True`` so HTML conversion runs with a closed network boundary out of the box. CLI presets such as ``--safe-mode`` and environment toggles like ``ALL2MD_DISABLE_NETWORK=1`` reinforce this posture without writing code.

NetworkFetchOptions
~~~~~~~~~~~~~~~~~~~

When you need remote assets, ``NetworkFetchOptions`` controls how fetching occurs:

.. code-block:: python

   from all2md import to_markdown, HtmlOptions
   from all2md.options import NetworkFetchOptions

   # Safe configuration: block all remote fetching
   safe_config = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=False  # Block all network requests
       )
   )

   # Selective allowlisting: only allow specific trusted domains
   allowlist_config = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=True,
           allowed_hosts=["cdn.example.com", "images.example.org"],
           require_https=True  # Force HTTPS for all requests
       )
   )

   # With size, timeout, and rate limits
   limited_config = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=True,
           allowed_hosts=["trusted-cdn.com"],
           require_https=True,
           network_timeout=5.0,          # 5 second timeout
           max_remote_asset_bytes=2*1024*1024,  # 2MB limit
           max_requests_per_second=3.0,
           max_concurrent_requests=2,
       )
   )

Allowlist Semantics
~~~~~~~~~~~~~~~~~~~

The ``allowed_hosts`` field has three distinct behaviors:

.. list-table:: Allowlist Behavior
   :header-rows: 1
   :widths: 20 40 40

   * - allowed_hosts Value
     - Behavior
     - Use Case
   * - ``None`` (default)
     - All hosts allowed (still subject to private-IP blocking)
     - Development, trusted sources
   * - ``[]`` (empty list)
     - All hosts blocked
     - Maximum security
   * - ``["host1", "host2"]``
     - Only specified hosts allowed
     - Controlled external resources

**Examples:**

.. code-block:: python

   # Allow all hosts (default, least secure)
   NetworkFetchOptions(
       allow_remote_fetch=True,
       allowed_hosts=None
   )

   # Block all hosts (equivalent to allow_remote_fetch=False)
   NetworkFetchOptions(
       allow_remote_fetch=True,
       allowed_hosts=[]
   )

   # Allow only specific CDNs
   NetworkFetchOptions(
       allow_remote_fetch=True,
       allowed_hosts=["cdn.jsdelivr.net", "unpkg.com"]
   )

HTTPS Enforcement
~~~~~~~~~~~~~~~~~

The ``require_https`` option forces all remote fetches to use HTTPS:

.. code-block:: python

   # Reject HTTP, only allow HTTPS
   network_opts = NetworkFetchOptions(
       allow_remote_fetch=True,
       require_https=True  # Blocks http:// URLs
   )

   html_opts = HtmlOptions(network=network_opts)
   markdown = to_markdown("webpage.html", parser_options=html_opts)

Size, Rate, and Timeout Limits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Protect against resource exhaustion with limits and throttling:

.. code-block:: python

   network_opts = NetworkFetchOptions(
       allow_remote_fetch=True,
       network_timeout=10.0,       # Timeout after 10 seconds
       max_remote_asset_bytes=5*1024*1024,  # 5MB max per asset (default: 20MB)
       max_requests_per_second=2.0,
       max_concurrent_requests=1,
   )

Global Network Disable
~~~~~~~~~~~~~~~~~~~~~~

For maximum security, disable all network access globally using the environment variable:

.. code-block:: bash

   # Disable all network fetching regardless of options
   export ALL2MD_DISABLE_NETWORK=1

   # Now all network requests will be blocked
   all2md webpage.html  # Won't fetch any remote images

This is useful in production environments where you want to ensure no network requests occur.

Private IP and Scheme Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Even when remote fetching is enabled, URLs pass through ``all2md.utils.network_security.validate_url_security``. The validator blocks:

* Private, loopback, and link-local IPv4/IPv6 ranges (``10.0.0.0/8``, ``192.168.0.0/16``, ``fc00::/7``)
* Cloud metadata endpoints and benchmarking ranges (``169.254.169.254``, ``198.18.0.0/15``)
* Non-HTTP(S) schemes such as ``file:``, ``ftp:``, ``javascript:``, or custom handlers
* Hosts not present in the allowlist when one is configured

Requests are also paced by ``network_security.RateLimiter`` so that a compromised document cannot perform high-volume reconnaissance.

Network Security Configuration Table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Quick reference for ``HtmlOptions.network.*`` settings:

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Option
     - Default
     - Description
   * - ``allow_remote_fetch``
     - ``False``
     - Master switch for remote fetching (disabled by default for security)
   * - ``allowed_hosts``
     - ``None``
     - Host allowlist (``None`` = all, ``[]`` = none, list = specific)
   * - ``require_https``
     - ``True``
     - Require HTTPS for all remote requests (enabled by default)
   * - ``network_timeout``
     - ``10.0``
     - Timeout in seconds for network requests
   * - ``max_remote_asset_bytes``
     - ``20971520``
     - Max download size per asset (20MB default)
   * - ``max_requests_per_second``
     - ``10.0``
     - Rate limit for remote asset fetching
   * - ``max_concurrent_requests``
     - ``5``
     - Maximum concurrent network requests

Remote Document Fetching
------------------------

Understanding RemoteInputOptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While ``NetworkFetchOptions`` controls fetching of assets (images, stylesheets) within documents, ``RemoteInputOptions`` controls fetching entire documents from HTTP(S) URLs. This allows you to directly convert web pages and remote documents:

.. code-block:: python

   from all2md import to_markdown
   from all2md.utils.input_sources import RemoteInputOptions

   # Convert a remote document
   options = RemoteInputOptions(
       allow_remote_input=True,
       require_https=True,
       follow_robots_txt="strict",
       user_agent="my-app/1.0"
   )

   markdown = to_markdown(
       "https://example.com/document.html",
       remote_input_options=options
   )

**Key Difference:**

- ``NetworkFetchOptions``: Controls asset fetching WITHIN documents (e.g., images in HTML)
- ``RemoteInputOptions``: Controls fetching the document itself from a URL

robots.txt Compliance (RFC 9309)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

all2md respects robots.txt files by default to ensure polite web crawling. The ``follow_robots_txt`` option controls how robots.txt rules are enforced:

.. code-block:: python

   from all2md.utils.input_sources import RemoteInputOptions

   # Strict mode: Block disallowed URLs (default)
   strict_options = RemoteInputOptions(
       allow_remote_input=True,
       follow_robots_txt="strict"  # Raises ValidationError if disallowed
   )

   # Warn mode: Log warning but proceed
   warn_options = RemoteInputOptions(
       allow_remote_input=True,
       follow_robots_txt="warn"  # Logs warning but continues
   )

   # Ignore mode: Skip robots.txt checks
   ignore_options = RemoteInputOptions(
       allow_remote_input=True,
       follow_robots_txt="ignore"  # No robots.txt validation
   )

**Policy Modes:**

.. list-table:: robots.txt Policy Modes
   :header-rows: 1
   :widths: 20 80

   * - Mode
     - Behavior
   * - ``strict``
     - Blocks access with ``ValidationError`` if robots.txt disallows the URL. Default and most respectful to site owners.
   * - ``warn``
     - Logs a warning but proceeds with the fetch. Useful for monitoring without blocking.
   * - ``ignore``
     - Skips robots.txt validation entirely. Use only for internal URLs or when you have explicit permission.

**RFC 9309 Compliance:**

The robots.txt checker follows RFC 9309 (Robot Exclusion Protocol):

* **404 Not Found**: Treats as "allow all" (no robots.txt = no restrictions)
* **5xx Server Errors**: Treats as "temporarily disallow all" (fail-safe behavior)
* **Network Errors**: Treats as "allow all" per RFC (don't punish sites for connectivity issues)
* **Crawl-delay**: Automatically enforces crawl-delay directives to respect rate limits
* **User-agent Matching**: Uses the ``user_agent`` from ``RemoteInputOptions`` for rule matching
* **Caching**: Caches robots.txt files for 1 hour to reduce redundant requests

.. code-block:: python

   # Example: Respectful web scraping with robots.txt
   from all2md import to_markdown
   from all2md.utils.input_sources import RemoteInputOptions

   options = RemoteInputOptions(
       allow_remote_input=True,
       follow_robots_txt="strict",  # Respect robots.txt
       user_agent="MyBot/1.0 (+https://example.com/bot-info)",
       timeout=10.0,
       max_size_bytes=20*1024*1024,  # 20MB limit
       require_https=True
   )

   try:
       # This will check robots.txt before fetching
       markdown = to_markdown(
           "https://example.com/article.html",
           remote_input_options=options
       )
   except ValidationError as e:
       print(f"Access denied by robots.txt: {e}")

**When to Use Each Mode:**

* **strict**: Public web scraping, respecting site owners (default, recommended)
* **warn**: Monitoring robot compliance without blocking operations
* **ignore**: Internal company URLs, APIs, or when you have explicit permission

RemoteInputOptions Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Complete reference for remote document fetching options:

.. list-table:: RemoteInputOptions Settings
   :header-rows: 1
   :widths: 30 15 55

   * - Option
     - Default
     - Description
   * - ``allow_remote_input``
     - ``False``
     - Master switch for fetching documents from URLs (disabled by default)
   * - ``follow_robots_txt``
     - ``"strict"``
     - robots.txt policy: ``"strict"``, ``"warn"``, or ``"ignore"``
   * - ``allowed_hosts``
     - ``None``
     - Host allowlist (``None`` = all, ``[]`` = none, list = specific)
   * - ``require_https``
     - ``True``
     - Require HTTPS for document URLs
   * - ``timeout``
     - ``10.0``
     - Request timeout in seconds
   * - ``max_size_bytes``
     - ``20971520``
     - Maximum document size (20MB default)
   * - ``user_agent``
     - ``"all2md-fetcher/1.0"``
     - User-Agent header (also used for robots.txt matching)

.. code-block:: python

   # Production-ready configuration
   from all2md.utils.input_sources import RemoteInputOptions

   production_options = RemoteInputOptions(
       allow_remote_input=True,
       # robots.txt enforcement
       follow_robots_txt="strict",
       user_agent="CompanyBot/2.0 (+https://company.com/bot-policy)",
       # Security
       require_https=True,
       allowed_hosts=["docs.company.com", "blog.company.com"],
       # Resource limits
       timeout=15.0,
       max_size_bytes=50*1024*1024  # 50MB for large docs
   )

robots.txt Best Practices
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Do:**

- ✅ Use default ``strict`` mode for public web scraping
- ✅ Provide a descriptive user-agent with contact information
- ✅ Cache results and avoid re-fetching robots.txt on every request
- ✅ Honor crawl-delay directives (handled automatically)
- ✅ Treat 5xx errors as temporary failures and respect them

**Don't:**

- ❌ Use ``ignore`` mode without explicit permission from site owner
- ❌ Spoof user-agents to bypass robots.txt rules
- ❌ Ignore crawl-delay directives
- ❌ Make excessive requests that burden the server
- ❌ Assume robots.txt absence means unrestricted access

**Example: Ethical Web Scraping:**

.. code-block:: python

   import time
   from all2md import to_markdown
   from all2md.utils.input_sources import RemoteInputOptions
   from all2md.exceptions import ValidationError

   # Respectful bot configuration
   bot_options = RemoteInputOptions(
       allow_remote_input=True,
       follow_robots_txt="strict",
       user_agent="ResearchBot/1.0 (+https://university.edu/research-policy)",
       require_https=True,
       timeout=30.0
   )

   urls = [
       "https://example.com/article1.html",
       "https://example.com/article2.html",
       "https://example.com/article3.html"
   ]

   for url in urls:
       try:
           # robots.txt is checked automatically
           markdown = to_markdown(url, remote_input_options=bot_options)

           # Process markdown...
           print(f"✓ Converted {url}")

           # Additional politeness: delay between requests
           # (crawl-delay from robots.txt is handled automatically)
           time.sleep(1.0)

       except ValidationError as e:
           # robots.txt blocked this URL
           print(f"✗ Blocked by robots.txt: {url}")
           print(f"  Reason: {e}")
           continue

       except Exception as e:
           print(f"✗ Error converting {url}: {e}")
           continue

Local File Access Security
--------------------------

Controlling file:// URLs
~~~~~~~~~~~~~~~~~~~~~~~~~

Documents may reference local files using ``file://`` URLs. This can expose sensitive system files. By default ``DEFAULT_ALLOW_LOCAL_FILES = False`` and ``DEFAULT_ALLOW_CWD_FILES = False`` so HTML parsing cannot read from disk unless explicitly granted.

.. code-block:: python

   from all2md.options import HtmlOptions
   from all2md.options import LocalFileAccessOptions

   # Block all local file access (recommended for untrusted input)
   safe_config = HtmlOptions(
       local_files=LocalFileAccessOptions(
           allow_local_files=False
       )
   )

   # Allow only specific directories
   selective_config = HtmlOptions(
       local_files=LocalFileAccessOptions(
           allow_local_files=True,
           local_file_allowlist=["/safe/public/images", "/var/www/assets"],
           local_file_denylist=["/etc", "/home", "/root"]
       )
   )

   # Allow current working directory only
   cwd_only_config = HtmlOptions(
       local_files=LocalFileAccessOptions(
           allow_local_files=False,
           allow_cwd_files=True  # Only files in CWD
       )
   )

Directory Allowlist/Denylist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Control which directories can be accessed:

.. code-block:: python

   local_opts = LocalFileAccessOptions(
       allow_local_files=True,
       # Explicitly allowed directories
       local_file_allowlist=[
           "/app/public/images",
           "/tmp/uploads"
       ],
       # Explicitly blocked directories (takes precedence)
       local_file_denylist=[
           "/etc",
           "/home",
           "/root",
           "/var/secrets"
       ]
   )

**Precedence Rules:**

1. Denylist is checked first - if path matches, access is denied
2. If allowlist is provided, path must match an allowed directory
3. If no allowlist and not denied, access is granted (when ``allow_local_files=True``)

Archive Security
----------------

Handling ZIP-based formats
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many office formats (``.docx``, ``.pptx``, ``.xlsx``) and EPUB bundles are ZIP archives. all2md validates archives before extraction to mitigate decompression bombs and path traversal attempts:

.. code-block:: python

   from all2md import to_markdown
   from all2md.utils.security import validate_zip_archive

   # Validate before processing
   try:
       validate_zip_archive(
           archive_path="suspicious.epub",  # EPUB files are ZIP archives
           max_uncompressed_size=100*1024*1024,  # 100MB limit
           max_compression_ratio=100  # Flag if compression > 100:1
       )
       # Safe to process
       markdown = to_markdown("suspicious.epub")
   except SecurityError as e:
       print(f"Archive validation failed: {e}")

Quick facts:

.. list-table:: Archive validation safeguards
   :header-rows: 1
   :widths: 30 70

   * - Check
     - Purpose
   * - Total and per-file size caps
     - Prevent archive bombs or payloads that exhaust disk/memory resources
   * - Compression ratio threshold
     - Flags suspicious archives that expand disproportionately (classic ZIP bombs)
   * - Directory traversal rejection
     - Blocks ``../`` paths that could overwrite or read files outside the extraction root
   * - Optional MIME allowlists
     - Focus processing on expected content types

Choose validation thresholds based on your deployment’s storage limits. For extremely risky inputs, pair validation with a sandboxed extraction directory mounted with minimal privileges.

CLI Security Presets
--------------------

The CLI provides security presets for common use cases:

Strict HTML Sanitization
~~~~~~~~~~~~~~~~~~~~~~~~

Remove all potentially dangerous HTML elements and attributes:

.. code-block:: bash

   # Strip scripts, styles, and other dangerous elements
   all2md webpage.html --strict-html-sanitize

This enables ``HtmlOptions.strip_dangerous_elements=True`` which removes:

* ``<script>`` tags
* ``<style>`` tags
* **All** event handler attributes (onclick, onload, onerror, onmouseover, onkeydown, etc.)
* ``<iframe>`` and ``<embed>`` tags
* ``<object>`` and ``<form>`` tags

**Comprehensive Event Handler Protection:**

The sanitizer uses pattern-based detection to block all HTML5 event handlers:

* **Window Events:** onload, onunload, onbeforeunload, onhashchange, onmessage
* **Form Events:** onsubmit, onchange, oninput, oninvalid, onreset, onselect
* **Mouse Events:** onclick, onmouseover, onmouseenter, onmouseleave, onmousedown, onmouseup, oncontextmenu
* **Keyboard Events:** onkeydown, onkeyup, onkeypress
* **Drag & Drop:** ondrag, ondrop, ondragstart, ondragend, ondragover
* **Media Events:** onplay, onpause, onended, onvolumechange, ontimeupdate
* **Clipboard Events:** oncopy, oncut, onpaste
* **Animation Events:** onanimationstart, onanimationend, ontransitionend
* **And 60+ more event handlers...**

Pattern matching catches even vendor-specific or future event handlers (any attribute starting with ``on`` followed by an alphabetic event name).

**JavaScript Framework Attribute Protection:**

For additional security when output may be re-rendered with JavaScript frameworks:

.. code-block:: python

   from all2md import to_markdown, HtmlOptions

   # Maximum XSS protection including framework attributes
   options = HtmlOptions(
       strip_dangerous_elements=True,      # Remove script, style, event handlers
       strip_framework_attributes=True,    # Remove framework directives
   )

   markdown = to_markdown(html_doc, parser_options=options)

When ``strip_framework_attributes=True``, the sanitizer also removes:

* **Alpine.js:** x-data, x-html, x-bind, x-on, x-text, x-model, x-if, x-for, x-init
* **Vue.js:** v-html, v-bind, v-on, v-model, v-if, v-for, @click, :href
* **Angular:** ng-bind-html, ng-click, ng-model, ng-if, ng-repeat, [attr], (event)
* **HTMX:** hx-get, hx-post, hx-put, hx-delete, hx-trigger, hx-vals, hx-on

These attributes are only dangerous if the output HTML is rendered in a browser with these frameworks present. For conversion to Markdown or plain text, framework attribute stripping is not necessary.

Safe Mode
~~~~~~~~~

Balanced security for general use:

.. code-block:: bash

   # Enable safe mode
   all2md document.html --safe-mode

Safe mode enables:

* HTML sanitization (``strip_dangerous_elements=True``)
* HTTPS enforcement (``require_https=True``)
* Blocks local file access (``allow_local_files=False``)
* Allows CWD files only (``allow_cwd_files=True``)

Paranoid Mode
~~~~~~~~~~~~~

Maximum security for untrusted input:

.. code-block:: bash

   # Maximum security lockdown
   all2md untrusted.html --paranoid-mode

Paranoid mode enables:

* All safe mode protections
* Blocks ALL network requests (``allow_remote_fetch=False``)
* Blocks ALL local files including CWD (``allow_cwd_files=False``)
* Strips JavaScript framework attributes (``strip_framework_attributes=True``)
* Strict timeouts and size limits
* Attachment mode set to ``skip`` (no file writes)

Recommended Secure Configurations
---------------------------------

Use the following starting points and adjust to match your threat model:

.. list-table:: Common security configurations
   :header-rows: 1
   :widths: 25 25 50

   * - Scenario
     - How to enable
     - Highlights
   * - Locked-down HTML ingestion
     - ``HtmlOptions`` with ``allow_remote_fetch=False``, ``allow_local_files=False``, ``strip_dangerous_elements=True``, ``strip_framework_attributes=True``; CLI ``--paranoid-mode``
     - Maximizes isolation by blocking network/local files and stripping all risky markup including event handlers and framework attributes
   * - Balanced safe defaults
     - CLI ``--safe-mode`` or preset ``security.safe``
     - Keeps HTTPS-only remote fetch, sanitizes HTML, and limits attachments while allowing opt-in flexibility
   * - Trusted-source pipeline
     - Allowlist trusted hosts/directories, enable attachments with output dir
     - Maintains protections against private IPs and dangerous schemes but relaxes access for vetted content

Security Best Practices
-----------------------

Library Integration
~~~~~~~~~~~~~~~~~~~

When integrating all2md into a web application:

.. code-block:: python

   from all2md import to_markdown, HtmlOptions, PdfOptions
   from all2md.options import NetworkFetchOptions, LocalFileAccessOptions
   import tempfile
   import os

   def convert_uploaded_document(file_data: bytes, filename: str) -> str:
       """Safely convert user-uploaded document."""

       # Validate file size
       MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
       if len(file_data) > MAX_FILE_SIZE:
           raise ValueError("File too large")

       # Determine file type
       ext = os.path.splitext(filename)[1].lower()

       # Configure security options
       if ext in ['.html', '.htm', '.mhtml']:
           options = HtmlOptions(
               strip_dangerous_elements=True,
               network=NetworkFetchOptions(
                   allow_remote_fetch=False  # Block SSRF
               ),
               local_files=LocalFileAccessOptions(
                   allow_local_files=False  # Block local file access
               ),
               attachment_mode='skip'  # Don't download any files
           )
       else:
           # PDF, DOCX, etc. - use safe defaults
           options = PdfOptions(
               attachment_mode='skip'  # No downloads
           )

       # Process in temporary file
       with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
           tmp.write(file_data)
           tmp_path = tmp.name

       try:
           markdown = to_markdown(tmp_path, parser_options=options)

           # Limit output size (prevent DoS)
           MAX_OUTPUT = 1024 * 1024  # 1MB
           if len(markdown) > MAX_OUTPUT:
               markdown = markdown[:MAX_OUTPUT] + "\n\n[Output truncated]"

           return markdown
       finally:
           os.unlink(tmp_path)

Processing Untrusted HTML
~~~~~~~~~~~~~~~~~~~~~~~~~

HTML documents are particularly risky. Always use strict settings:

.. code-block:: python

   from all2md import to_markdown, HtmlOptions
   from all2md.options import NetworkFetchOptions, LocalFileAccessOptions

   # Maximum security HTML processing
   untrusted_html_options = HtmlOptions(
       extract_title=True,
       strip_dangerous_elements=True,      # Remove script, style, event handlers
       strip_framework_attributes=True,     # Remove framework directives (if re-rendering HTML)
       network=NetworkFetchOptions(
           allow_remote_fetch=False  # No network access
       ),
       local_files=LocalFileAccessOptions(
           allow_local_files=False,
           allow_cwd_files=False
       ),
       attachment_mode='skip'
   )

   markdown = to_markdown(untrusted_html, parser_options=untrusted_html_options)

Content from Known Sources
~~~~~~~~~~~~~~~~~~~~~~~~~~

For trusted sources, you can relax restrictions:

.. code-block:: python

   # Processing internal documentation
   trusted_options = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=True,
           allowed_hosts=["internal-cdn.company.com"],  # Company CDN only
           require_https=True
       ),
       local_files=LocalFileAccessOptions(
           allow_local_files=True,
           local_file_allowlist=["/company/docs/images"]
       ),
       attachment_mode='download',
       attachment_output_dir='./downloaded_images'
   )

Automated Batch Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~

When processing multiple files, validate before conversion:

.. code-block:: python

   from pathlib import Path
   from all2md import to_markdown
   from all2md.utils.security import validate_zip_archive

   def safe_batch_convert(files: list[Path]) -> dict:
       results = {}

       for file_path in files:
           try:
               # Validate ZIP-based formats
               if file_path.suffix in ['.epub', '.docx', '.pptx', '.xlsx']:
                   validate_zip_archive(
                       str(file_path),
                       max_uncompressed_size=100*1024*1024
                   )

               # Convert with safe options
               markdown = to_markdown(
                   file_path,
                   attachment_mode='skip',  # No downloads
                   extract_metadata=False    # Avoid metadata exploits
               )
               results[str(file_path)] = {"success": True, "content": markdown}

           except Exception as e:
               results[str(file_path)] = {"success": False, "error": str(e)}

       return results

Security Checklist
------------------

When processing documents from untrusted sources, ensure:

**Network Security:**

- [ ] Set ``allow_remote_fetch=False`` or use strict allowlist
- [ ] Enable ``require_https=True`` if fetching allowed
- [ ] Set reasonable ``network_timeout`` values
- [ ] Limit ``max_remote_asset_bytes`` appropriately
- [ ] Consider ``ALL2MD_DISABLE_NETWORK`` environment variable in production
- [ ] Monitor request rate with ``max_requests_per_second`` and ``max_concurrent_requests``

**Remote Document Fetching:**

- [ ] Keep ``follow_robots_txt="strict"`` for public web scraping (default)
- [ ] Provide descriptive ``user_agent`` with contact information
- [ ] Set ``allow_remote_input=False`` when not fetching documents from URLs
- [ ] Use ``allowed_hosts`` to restrict to trusted domains
- [ ] Enable ``require_https=True`` for remote documents (default)
- [ ] Set appropriate ``timeout`` and ``max_size_bytes`` limits

**Local File Security:**

- [ ] Set ``allow_local_files=False`` for untrusted input
- [ ] Use ``local_file_allowlist`` for known safe directories
- [ ] Add sensitive paths to ``local_file_denylist``
- [ ] Carefully consider ``allow_cwd_files`` based on your threat model

**Content Security:**

- [ ] Enable ``strip_dangerous_elements`` for HTML (removes script, style, event handlers)
- [ ] Enable ``strip_framework_attributes`` if re-rendering HTML with frameworks
- [ ] Set ``attachment_mode='skip'`` to prevent file writes
- [ ] Validate file sizes before processing
- [ ] Limit output size to prevent DoS
- [ ] Validate archives before extraction

**Production Deployment:**

- [ ] Process uploads in isolated temporary directories
- [ ] Run converter with minimal privileges
- [ ] Set resource limits (memory, CPU, disk)
- [ ] Monitor for unusual activity or errors
- [ ] Log security-relevant events
- [ ] Keep all2md and dependencies updated

For format-specific security considerations, see the :doc:`formats` guide. For configuration details, see the :doc:`options` reference.

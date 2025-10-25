Threat Model and Security Architecture
=======================================

This document describes all2md's security architecture, threat model, and defense mechanisms for processing untrusted documents. It complements the :doc:`security` guide by providing deeper insight into the security design philosophy and attack surface analysis.

.. contents::
   :local:
   :depth: 3

Overview
--------

all2md is designed to safely process documents from potentially untrusted sources, such as user uploads, web scraping, or automated data pipelines. The security model assumes that:

* **Documents may be malicious:** Input files can contain crafted content designed to exploit vulnerabilities
* **Network access is risky:** Documents may reference URLs to internal services or malicious external resources
* **Local filesystem access is sensitive:** Documents may attempt to access private files via file:// URLs
* **Resource exhaustion is a concern:** Malicious files may be designed to consume excessive CPU, memory, or disk space

Threat Model
------------

Trust Boundaries
~~~~~~~~~~~~~~~~

all2md operates with the following trust boundaries:

.. list-table:: Trust Boundaries
   :header-rows: 1
   :widths: 25 35 40

   * - Component
     - Trust Level
     - Risk
   * - Input documents
     - **Untrusted**
     - May contain malicious content
   * - Conversion code
     - **Trusted**
     - Developed with security review
   * - Output markdown
     - **Sanitized**
     - Safe for viewing/rendering
   * - Local filesystem
     - **Protected**
     - Requires explicit permission
   * - External networks
     - **Untrusted**
     - May be malicious or compromised

Assumptions
~~~~~~~~~~~

The security model makes these assumptions:

1. **Server Environment:** all2md runs in a server or automated environment where multiple untrusted documents are processed
2. **Attacker Goals:** Attackers may attempt SSRF, local file disclosure, denial of service, or remote code execution
3. **Defense in Depth:** Multiple layers of protection are preferred over single points of control
4. **Fail Secure:** When security validation fails, the system should deny access rather than allow
5. **Principle of Least Privilege:** Access to resources (network, filesystem) is denied by default

Attack Vectors and Defenses
----------------------------

1. Server-Side Request Forgery (SSRF)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attack Description
^^^^^^^^^^^^^^^^^^

Malicious documents (HTML, PDF, EPUB, etc.) may contain URLs pointing to internal network resources that the server can access but external attackers cannot. When all2md fetches these resources (e.g., to download images), it inadvertently acts as a proxy for the attacker.

**Common SSRF Targets:**

* Cloud metadata services: ``http://169.254.169.254/latest/meta-data/``
* Internal APIs: ``http://localhost:8080/admin``
* Database services: ``http://internal-db:5432/``
* Network scanning: ``http://10.0.0.1/``, ``http://192.168.1.1/``

**Example Attack:**

.. code-block:: html

   <!-- Malicious HTML document -->
   <img src="http://169.254.169.254/latest/meta-data/iam/security-credentials/">

Defense Mechanisms
^^^^^^^^^^^^^^^^^^

all2md provides multiple SSRF defenses via ``NetworkFetchOptions``:

1. **Disable Remote Fetching (Strongest):**

   .. code-block:: python

      from all2md import to_markdown, HtmlOptions
      from all2md.options import NetworkFetchOptions

      safe_config = HtmlOptions(
          network=NetworkFetchOptions(
              allow_remote_fetch=False  # Block ALL network requests
          )
      )

      result = to_markdown(html_doc, parser_options=safe_config)

2. **Allowlist Trusted Hosts:**

   .. code-block:: python

      limited_config = HtmlOptions(
          network=NetworkFetchOptions(
              allow_remote_fetch=True,
              allowed_hosts=["cdn.example.com", "images.example.org"],
              require_https=True  # Prevent downgrade attacks
          )
      )

3. **Block Internal Networks:**

   .. code-block:: python

      # Empty allowlist blocks ALL hosts
      blocked_config = HtmlOptions(
          network=NetworkFetchOptions(
              allow_remote_fetch=True,
              allowed_hosts=[]  # Block everything
          )
      )

**Implementation Details:**

* ``utils/network_security.py``: ``fetch_image_securely()`` validates URLs before fetching
* Blocks private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
* Blocks localhost (127.0.0.0/8, ::1)
* Blocks cloud metadata IPs (169.254.169.254)
* Enforces HTTPS when ``require_https=True``
* Enforces size limits via ``max_remote_asset_bytes``
* Enforces timeouts via ``network_timeout``

**Risk Level:** High (without protections)

**Mitigation Effectiveness:** High (when configured properly)

---

2. Local File Disclosure
~~~~~~~~~~~~~~~~~~~~~~~~~

Attack Description
^^^^^^^^^^^^^^^^^^

Documents may reference local files via ``file://`` URLs, attempting to read sensitive files from the server's filesystem and include them in the output.

**Common Targets:**

* SSH keys: ``file:///home/user/.ssh/id_rsa``
* Configuration files: ``file:///etc/passwd``, ``file:///etc/shadow``
* Application secrets: ``file:///app/.env``
* Source code: ``file:///app/config/database.yml``

**Example Attack:**

.. code-block:: html

   <!-- Malicious HTML with file:// URL -->
   <img src="file:///etc/passwd" alt="system password file">

Defense Mechanisms
^^^^^^^^^^^^^^^^^^

all2md provides ``LocalFileAccessOptions`` to control file:// URL access:

1. **Block All Local Files (Default):**

   .. code-block:: python

      from all2md import to_markdown, HtmlOptions
      from all2md.options import LocalFileAccessOptions

      secure_config = HtmlOptions(
          local_files=LocalFileAccessOptions(
              allow_local_files=False  # Default: block all file:// URLs
          )
      )

2. **Allow Only CWD Files:**

   .. code-block:: python

      cwd_only_config = HtmlOptions(
          local_files=LocalFileAccessOptions(
              allow_local_files=True,
              allow_cwd_files=True,  # Only files in current working directory
              local_file_allowlist=[],  # No other directories
              local_file_denylist=[]
          )
      )

3. **Allowlist Specific Directories:**

   .. code-block:: python

      allowlist_config = HtmlOptions(
          local_files=LocalFileAccessOptions(
              allow_local_files=True,
              allow_cwd_files=False,
              local_file_allowlist=["/app/public/images"],  # Only this dir
              local_file_denylist=["/app/secrets"]  # Explicit deny
          )
      )

**Implementation Details:**

* ``utils/security.py``: ``validate_local_file_access()`` checks file:// URLs
* ``parsers/html.py``: Validates file:// URLs before processing images
* Returns empty URL with alt text when access denied (prevents path leakage)
* Denylist takes precedence over allowlist
* Path traversal attempts (``../``) are resolved before validation

**Risk Level:** High (without protections)

**Mitigation Effectiveness:** High (when configured properly)

---

3. ZIP Bomb / Archive Exhaustion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attack Description
^^^^^^^^^^^^^^^^^^

Malicious archive files (DOCX, PPTX, EPUB, ODT) may contain extreme compression ratios, expanding from a small file to consume all available disk space or memory when extracted.

**Example:** A 42KB ZIP file that expands to 4.5GB (100,000:1 ratio)

Defense Mechanisms
^^^^^^^^^^^^^^^^^^

all2md provides built-in ZIP validation:

.. code-block:: python

   from all2md.utils.security import validate_zip_archive

   # Automatically called by DOCX, PPTX, EPUB, ODT parsers
   validate_zip_archive(
       zip_path,
       max_files=10000,        # Limit number of files
       max_file_size=100*1024*1024,  # 100MB per file
       max_compression_ratio=100.0    # 100:1 max ratio
   )

**Validation Checks:**

1. **File Count Limit:** Prevents ZIP files with excessive number of entries
2. **Individual File Size:** Limits size of each file within archive
3. **Compression Ratio:** Detects suspiciously high compression (potential bomb)
4. **Path Traversal:** Blocks files with ``../`` in paths (zip slip attack)

**Implementation Details:**

* ``utils/security.py``: ``validate_zip_archive()``
* Pre-validates before extraction
* Used by: DOCX, PPTX, EPUB, ODT, ODP parsers
* Raises ``ZipFileSecurityError`` on validation failure

**Risk Level:** Medium

**Mitigation Effectiveness:** High (automatic validation)

---

4. Resource Exhaustion / Denial of Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attack Description
^^^^^^^^^^^^^^^^^^

Malicious documents may be designed to consume excessive resources:

* **Large files:** Multi-gigabyte PDFs or images
* **Deeply nested structures:** HTML with 10,000 nested <div> elements
* **Infinite loops:** Self-referencing document structures
* **Memory bombs:** Uncompressed images or large embedded assets

Defense Mechanisms
^^^^^^^^^^^^^^^^^^

all2md provides multiple resource limits:

1. **File Size Limits:**

   .. code-block:: python

      from all2md import to_markdown, HtmlOptions

      limited_config = HtmlOptions(
          max_asset_bytes=5*1024*1024,  # 5MB max for images
          network=NetworkFetchOptions(
              max_remote_asset_bytes=2*1024*1024  # 2MB max for remote
          )
      )

2. **Network Timeouts:**

   .. code-block:: python

      timeout_config = HtmlOptions(
          network=NetworkFetchOptions(
              network_timeout=5.0  # 5 second timeout per request
          )
      )

3. **Processing Limits (Application Level):**

   Recommended to implement at application level:

   * Process timeout (kill conversion after N seconds)
   * Memory limits (cgroups, Docker memory limits)
   * Input file size limits (check before parsing)

**Implementation Details:**

* ``max_asset_bytes``: Enforced during image processing
* ``network_timeout``: Enforced during HTTP requests
* ``max_remote_asset_bytes``: Enforced during downloads
* Application should add additional limits (file size, processing time)

**Risk Level:** Medium

**Mitigation Effectiveness:** Medium (requires application-level limits too)

---

5. Path Traversal (Zip Slip)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attack Description
^^^^^^^^^^^^^^^^^^

Malicious ZIP archives (in DOCX, PPTX, EPUB) may contain files with paths like ``../../etc/passwd`` that extract outside the intended directory.

Defense Mechanisms
^^^^^^^^^^^^^^^^^^

* ``validate_zip_archive()`` checks all file paths
* Blocks any path containing ``../``
* Resolves all paths before validation
* Prevents extraction of dangerous files

**Risk Level:** Medium

**Mitigation Effectiveness:** High (automatic validation)

---

6. Cross-Site Scripting (XSS) via HTML Attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attack Description
^^^^^^^^^^^^^^^^^^

When processing HTML documents and re-rendering the output as HTML (or storing it for later HTML rendering), malicious HTML attributes can execute JavaScript code. This includes both standard HTML5 event handlers and JavaScript framework-specific attributes.

**Attack Vectors:**

1. **Event Handler Attributes:** HTML5 specifies 100+ event handler attributes that can execute JavaScript
2. **Framework Attributes:** JavaScript frameworks (Alpine.js, Vue.js, Angular, HTMX) use special attributes that execute code in framework contexts
3. **Data Attributes:** Framework-prefixed data attributes (``data-x-*``, ``data-v-*``) can execute code

**Example Attacks:**

.. code-block:: html

   <!-- Standard event handlers -->
   <div onclick="alert('XSS')">Click me</div>
   <img src="x" onerror="stealCookies()">
   <body onload="maliciousCode()">

   <!-- Less common but still dangerous -->
   <div onmouseover="trackUser()">Hover</div>
   <input onfocus="captureInput()">
   <div onanimationstart="exploit()">Animated</div>

   <!-- Framework attributes (dangerous in framework contexts) -->
   <div x-html="userContent">Alpine.js XSS</div>
   <div v-html="maliciousHTML">Vue.js XSS</div>
   <div ng-bind-html="unsafeContent">Angular XSS</div>

Defense Mechanisms
^^^^^^^^^^^^^^^^^^

all2md provides comprehensive attribute sanitization via ``HtmlOptions.strip_dangerous_elements`` and ``HtmlOptions.strip_framework_attributes``:

1. **Event Handler Detection (Automatic with strip_dangerous_elements):**

   .. code-block:: python

      from all2md import to_markdown, HtmlOptions

      # Remove all dangerous elements AND event handler attributes
      safe_config = HtmlOptions(
          strip_dangerous_elements=True  # Removes script, style, event handlers
      )

      result = to_markdown(html_doc, parser_options=safe_config)

2. **Framework Attribute Stripping (Opt-in):**

   .. code-block:: python

      # Additional protection for framework-aware contexts
      framework_safe_config = HtmlOptions(
          strip_dangerous_elements=True,
          strip_framework_attributes=True  # Remove x-*, v-*, ng-*, hx-*, etc.
      )

      result = to_markdown(html_doc, parser_options=framework_safe_config)

**Protected Event Handlers (Comprehensive List):**

All HTML5 event handlers are detected via pattern matching:

* **Window Events:** onload, onunload, onbeforeunload, onhashchange, onmessage, etc.
* **Form Events:** onsubmit, onchange, oninput, oninvalid, onreset, onselect
* **Mouse Events:** onclick, onmouseover, onmouseenter, onmouseleave, onmousedown, onmouseup, etc.
* **Keyboard Events:** onkeydown, onkeyup, onkeypress
* **Drag & Drop:** ondrag, ondrop, ondragstart, ondragend, ondragover, etc.
* **Media Events:** onplay, onpause, onended, onvolumechange, ontimeupdate, etc.
* **Clipboard Events:** oncopy, oncut, onpaste
* **Animation Events:** onanimationstart, onanimationend, onanimationiteration, ontransitionend
* **Touch Events:** ontouchstart, ontouchend, ontouchmove, ontouchcancel
* **And 60+ more...**

**Protected Framework Attributes:**

When ``strip_framework_attributes=True``:

* **Alpine.js:** x-data, x-html, x-bind, x-on, x-text, x-model, x-if, x-for, x-init, etc.
* **Vue.js:** v-html, v-bind, v-on, v-model, v-if, v-for, @click, :href, etc.
* **Angular:** ng-bind-html, ng-click, ng-model, ng-if, ng-repeat, [attr], (event), etc.
* **HTMX:** hx-get, hx-post, hx-put, hx-delete, hx-trigger, hx-vals, hx-on, etc.

**Implementation Details:**

* Pattern-based detection catches all ``on*`` attributes (not just a hardcoded list)
* Smart pattern matching avoids false positives (e.g., ``one-time``, ``only-when``)
* Event handlers must follow HTML5 naming: ``on`` + alphabetic event name (no hyphens)
* Framework attributes are only stripped when explicitly enabled (opt-in for backward compatibility)
* Sanitization occurs in both ``is_element_safe()`` validation and ``_basic_sanitize_html_string()``

**Risk Level:** High (if HTML output is re-rendered in browsers)

**Mitigation Effectiveness:** High (comprehensive pattern-based detection)

**When to Enable Framework Stripping:**

* Output HTML will be rendered in browsers with JavaScript frameworks installed
* Processing user-generated content for display in framework-based web apps
* Converting HTML for storage in CMS systems that use JavaScript frameworks
* Maximum security posture for untrusted input

**When Framework Stripping is NOT Needed:**

* Converting to Markdown for plain text viewing
* Output will not be re-rendered as HTML
* No JavaScript frameworks present in rendering context
* Processing purely static HTML documents

---

Security Options Quick Reference
---------------------------------

This table maps each attack vector to the relevant security options:

.. list-table:: Attack Vectors and Mitigations
   :header-rows: 1
   :widths: 25 30 45

   * - Attack Vector
     - Primary Defense
     - Configuration
   * - SSRF (Internal Network)
     - NetworkFetchOptions
     - ``allow_remote_fetch=False`` or ``allowed_hosts=[]``
   * - SSRF (Cloud Metadata)
     - NetworkFetchOptions
     - Built-in blocking of 169.254.169.254
   * - Local File Disclosure
     - LocalFileAccessOptions
     - ``allow_local_files=False`` (default)
   * - ZIP Bomb
     - validate_zip_archive
     - Automatic (max_compression_ratio=100)
   * - Resource Exhaustion
     - Size/Timeout Limits
     - ``max_asset_bytes``, ``network_timeout``
   * - Path Traversal
     - validate_zip_archive
     - Automatic (blocks ``../``)
   * - XSS (Event Handlers)
     - strip_dangerous_elements
     - ``strip_dangerous_elements=True`` (removes all on* attributes)
   * - XSS (Framework Attrs)
     - strip_framework_attributes
     - ``strip_framework_attributes=True`` (opt-in for frameworks)

Best Practices
--------------

For Untrusted Input
~~~~~~~~~~~~~~~~~~~

When processing documents from untrusted sources (user uploads, web scraping):

.. code-block:: python

   from all2md import to_markdown, HtmlOptions
   from all2md.options import NetworkFetchOptions, LocalFileAccessOptions

   # Paranoid mode: maximum security
   paranoid_config = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=False  # Block all network access
       ),
       local_files=LocalFileAccessOptions(
           allow_local_files=False  # Block all file:// access
       ),
       strip_dangerous_elements=True,  # Remove <script>, <iframe>, event handlers
       strip_framework_attributes=True,  # Remove x-*, v-*, ng-*, hx-* attributes
       attachment_mode="alt_text"  # Don't download anything
   )

   result = to_markdown(untrusted_doc, parser_options=paranoid_config)

For Trusted Input
~~~~~~~~~~~~~~~~~

When processing documents from trusted sources (internal systems):

.. code-block:: python

   # Trusted mode: enable features with safeguards
   trusted_config = HtmlOptions(
       network=NetworkFetchOptions(
           allow_remote_fetch=True,
           allowed_hosts=["cdn.mycompany.com"],  # Limit to known CDN
           require_https=True,
           network_timeout=10.0,
           max_remote_asset_bytes=10*1024*1024  # 10MB limit
       ),
       local_files=LocalFileAccessOptions(
           allow_local_files=True,
           allow_cwd_files=True,
           local_file_allowlist=["/app/data/images"],
           local_file_denylist=["/etc", "/var"]
       )
   )

Application-Level Protections
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Beyond all2md's built-in protections, implement these at the application level:

1. **Input Validation:**

   .. code-block:: python

      import os

      # Check file size before parsing
      max_input_size = 50 * 1024 * 1024  # 50MB
      if os.path.getsize(input_file) > max_input_size:
          raise ValueError("File too large")

2. **Processing Timeout:**

   .. code-block:: python

      import signal

      def timeout_handler(signum, frame):
          raise TimeoutError("Conversion took too long")

      # Set 30 second timeout
      signal.signal(signal.SIGALRM, timeout_handler)
      signal.alarm(30)

      try:
          result = to_markdown(document)
      finally:
          signal.alarm(0)  # Cancel alarm

3. **Resource Limits (Docker):**

   .. code-block:: yaml

      # docker-compose.yml
      services:
        converter:
          image: my-app
          mem_limit: 1g
          cpus: 1.0
          pids_limit: 100

4. **Sandbox Environment:**

   * Run conversions in isolated containers
   * Use separate user accounts with minimal permissions
   * Mount filesystem read-only where possible
   * Disable network access at OS level if not needed

Security Checklist
------------------

Use this checklist when deploying all2md for untrusted input:

.. code-block:: text

   [ ] Set allow_remote_fetch=False or use allowed_hosts allowlist
   [ ] Set allow_local_files=False (or strict allowlist)
   [ ] Set strip_dangerous_elements=True for HTML (removes script, style, event handlers)
   [ ] Set strip_framework_attributes=True if re-rendering HTML with frameworks
   [ ] Set max_asset_bytes to reasonable limit
   [ ] Set network_timeout to prevent hangs
   [ ] Implement application-level file size limits
   [ ] Implement processing timeouts
   [ ] Run in isolated/sandboxed environment
   [ ] Monitor for unusual CPU/memory/network usage
   [ ] Review logs for security warnings

Reporting Security Issues
-------------------------

If you discover a security vulnerability in all2md:

1. **Do not** open a public issue on GitHub
2. Email security concerns to: (contact method TBD)
3. Include: affected versions, attack vector, proof of concept
4. Allow reasonable time for patch before disclosure

See Also
--------

* :doc:`security` - Detailed security configuration guide
* :doc:`options` - Complete options reference
* :doc:`troubleshooting` - Common security errors and solutions

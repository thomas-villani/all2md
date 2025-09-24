Installation Guide
==================

System Requirements
-------------------

* **Python**: 3.12 or higher
* **Operating System**: Windows, macOS, Linux
* **Memory**: Minimum 512MB RAM (more for large documents)

Basic Installation
------------------

Install mdparse from PyPI using pip:

.. code-block:: bash

   pip install mdparse

This will install mdparse with its core dependencies. Optional dependencies for specific formats are installed automatically when needed.

Development Installation
------------------------

For development or contributing to the project:

.. code-block:: bash

   git clone https://github.com/thomas-villani/mdparse.git
   cd mdparse
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .[dev]

This installs mdparse in editable mode with development tools.

Dependencies
------------

Core Dependencies
~~~~~~~~~~~~~~~~~

mdparse automatically installs these core dependencies:

* **PyMuPDF** (≥1.26.4) - PDF processing and table detection
* **python-docx** (≥1.2.0) - Word document handling
* **python-pptx** (≥1.0.2) - PowerPoint processing
* **beautifulsoup4** (≥4.13.5) - HTML parsing
* **pandas** (≥2.3.2) - Spreadsheet processing
* **standard-imghdr** (≥3.13.0) - Image format detection

Development Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~

For development work, additional tools are installed:

* **mypy** (≥1.18.2) - Type checking
* **pytest** (≥8.4.2) - Testing framework
* **ruff** (≥0.13.1) - Linting and formatting
* **sphinx** (≥8.2.3) - Documentation generation
* **sphinx-rtd-theme** (≥3.0.2) - Documentation theme

Verifying Installation
----------------------

Test your installation:

.. code-block:: python

   import mdparse
   print(f"mdparse version: {mdparse.__version__}")

   # Test basic functionality
   from mdparse import parse_file
   from io import StringIO

   # Test with a simple text file
   test_content = "# Hello World\n\nThis is a test."
   test_file = StringIO(test_content)
   result = parse_file(test_file, "test.md")
   print("Installation successful!")

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**Import Errors**
   If you get import errors for specific formats, try:

   .. code-block:: bash

      pip install --upgrade mdparse

**Permission Errors**
   On some systems, you might need to use:

   .. code-block:: bash

      pip install --user mdparse

**Virtual Environment Issues**
   Always use a virtual environment for development:

   .. code-block:: bash

      python -m venv mdparse-env
      source mdparse-env/bin/activate
      pip install mdparse

**PyMuPDF Installation Issues**
   PyMuPDF requires specific system libraries. If installation fails:

   - On Ubuntu/Debian: ``sudo apt-get install build-essential``
   - On CentOS/RHEL: ``sudo yum groupinstall "Development Tools"``
   - On macOS: Install Xcode command line tools

Platform-Specific Notes
------------------------

Windows
~~~~~~~

* Requires Visual C++ build tools for some dependencies
* Use PowerShell or Command Prompt for installation
* Virtual environments: ``.venv\Scripts\activate``

macOS
~~~~~

* May require Xcode command line tools: ``xcode-select --install``
* Homebrew users: ``brew install python``
* Virtual environments: ``source .venv/bin/activate``

Linux
~~~~~

* Requires development packages: ``build-essential`` (Ubuntu) or ``gcc`` (CentOS)
* Some distributions may need ``python3-dev`` or ``python3-devel``
* Virtual environments: ``source .venv/bin/activate``

Docker Installation
-------------------

Use mdparse in a Docker container:

.. code-block:: dockerfile

   FROM python:3.12-slim

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       build-essential \
       && rm -rf /var/lib/apt/lists/*

   # Install mdparse
   RUN pip install mdparse

   # Your application code
   COPY . /app
   WORKDIR /app

Upgrading
---------

To upgrade to the latest version:

.. code-block:: bash

   pip install --upgrade mdparse

To upgrade to a specific version:

.. code-block:: bash

   pip install mdparse==1.2.0

Uninstalling
------------

To remove mdparse:

.. code-block:: bash

   pip uninstall mdparse

This will remove mdparse but keep its dependencies. To remove dependencies that are no longer needed, use:

.. code-block:: bash

   pip autoremove
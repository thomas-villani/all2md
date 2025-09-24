Installation Guide
==================

System Requirements
-------------------

* **Python**: 3.12 or higher
* **Operating System**: Windows, macOS, Linux
* **Memory**: Minimum 512MB RAM (more for large documents)

Basic Installation
------------------

Install all2md from PyPI using pip:

.. code-block:: bash

   pip install all2md

This will install all2md with its core dependencies. Optional dependencies for specific formats are installed automatically when needed.

Development Installation
------------------------

For development or contributing to the project:

.. code-block:: bash

   git clone https://github.com/thomas-villani/all2md.git
   cd all2md
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .[dev]

This installs all2md in editable mode with development tools.

Dependencies
------------

Core Dependencies
~~~~~~~~~~~~~~~~~

all2md automatically installs these core dependencies:

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

   import all2md
   print(f"all2md version: {all2md.__version__}")

   # Test basic functionality
   from all2md import parse_file
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

      pip install --upgrade all2md

**Permission Errors**
   On some systems, you might need to use:

   .. code-block:: bash

      pip install --user all2md

**Virtual Environment Issues**
   Always use a virtual environment for development:

   .. code-block:: bash

      python -m venv all2md-env
      source all2md-env/bin/activate
      pip install all2md

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

Use all2md in a Docker container:

.. code-block:: dockerfile

   FROM python:3.12-slim

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       build-essential \
       && rm -rf /var/lib/apt/lists/*

   # Install all2md
   RUN pip install all2md

   # Your application code
   COPY . /app
   WORKDIR /app

Upgrading
---------

To upgrade to the latest version:

.. code-block:: bash

   pip install --upgrade all2md

To upgrade to a specific version:

.. code-block:: bash

   pip install all2md==1.2.0

Uninstalling
------------

To remove all2md:

.. code-block:: bash

   pip uninstall all2md

This will remove all2md but keep its dependencies. To remove dependencies that are no longer needed, use:

.. code-block:: bash

   pip autoremove
Installation Guide
==================

This guide covers all installation methods for all2md, from basic setup to development environments.

Requirements
------------

* **Python 3.12 or later**
* pip (comes with Python)
* Optional: git (for development installation)

Quick Install
-------------

For most users, start with the basic installation:

.. code-block:: bash

   pip install all2md

This includes support for:

* HTML documents
* CSV/TSV files
* Text files (200+ formats)
* Images (PNG, JPEG, GIF)

Optional Dependencies
---------------------

all2md uses optional dependencies to keep the base installation lightweight. Install only the formats you need:

PDF Support
~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[pdf]

**Dependencies:** PyMuPDF

**Formats:** PDF documents with advanced table detection, image extraction, and text formatting

Word Documents
~~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[docx]

**Dependencies:** python-docx

**Formats:** Microsoft Word .docx files with full formatting preservation

PowerPoint Presentations
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[pptx]

**Dependencies:** python-pptx

**Formats:** Microsoft PowerPoint .pptx files with slide-by-slide extraction

HTML Documents
~~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[html]

**Dependencies:** BeautifulSoup4, httpx

**Formats:** HTML and MHTML files with intelligent content extraction

Email Files
~~~~~~~~~~~

Email support is built into the base installation - no additional dependencies required.

**Dependencies:** Built-in Python email libraries

**Formats:** Email .eml files with attachment handling and chain detection

EPUB E-books
~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[epub]

**Dependencies:** ebooklib

**Formats:** EPUB e-book files with chapter extraction and metadata

RTF Documents
~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[rtf]

**Dependencies:** pyth3

**Formats:** Rich Text Format files with formatting preservation

reStructuredText
~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[rst]

**Dependencies:** docutils

**Formats:** reStructuredText (.rst, .rest) files with full bidirectional support for Sphinx documentation

OpenDocument Formats
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[odf]

**Dependencies:** odfpy

**Formats:** OpenDocument Text (.odt) and Presentation (.odp) files

Spreadsheet Files
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install all2md[spreadsheet]

**Dependencies:** openpyxl for Excel files, built-in csv module for CSV/TSV

**Formats:** Excel .xlsx files, CSV and TSV files with unified processing

Jupyter Notebooks
~~~~~~~~~~~~~~~~~

Jupyter Notebook support is built into the base installation - no additional dependencies required.

**Dependencies:** Built-in Python json libraries

**Formats:** Jupyter Notebook .ipynb files with code, output, and markdown cells

Combined Installations
----------------------

Install Multiple Formats
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Common document formats
   pip install all2md[pdf,docx,html]

   # Office suite formats
   pip install all2md[pdf,docx,pptx,spreadsheet]

   # All supported formats
   pip install all2md[all]

All Dependencies
~~~~~~~~~~~~~~~~

The ``all`` extra includes every optional dependency:

.. code-block:: bash

   pip install all2md[all]

This is equivalent to:

.. code-block:: bash

   pip install all2md[pdf,docx,pptx,html,epub,rtf,rst,odf,spreadsheet]

**Note:** The ``eml`` and ``ipynb`` extras are not needed as these formats use built-in Python libraries.

Dependency Management
---------------------

all2md includes convenient command-line tools to manage optional dependencies after installation.

Check Dependencies
~~~~~~~~~~~~~~~~~~

Check which dependencies are currently installed:

.. code-block:: bash

   # Check all format dependencies
   all2md check-deps

   # Check specific format dependencies
   all2md check-deps pdf
   all2md check-deps docx

Install Dependencies
~~~~~~~~~~~~~~~~~~~~

Install missing dependencies directly from the command line:

.. code-block:: bash

   # Install all missing dependencies for all formats
   all2md install-deps

   # Install dependencies for specific format
   all2md install-deps pdf
   all2md install-deps docx

**Note:** Running ``all2md install-deps`` without specifying a format will install dependencies for ALL supported formats, equivalent to ``pip install all2md[all]``.

Development Installation
------------------------

For contributors or advanced users who want to modify all2md:

Prerequisites
~~~~~~~~~~~~~

.. code-block:: bash

   # Install git if not already installed
   # On Ubuntu/Debian:
   sudo apt-get install git

   # On macOS (with Homebrew):
   brew install git

   # On Windows:
   # Download from https://git-scm.com/

Clone and Install
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/thomas.villani/all2md.git
   cd all2md

   # Install in development mode with all dependencies
   pip install -e .[dev,all]

This installs:

* All format dependencies
* Development tools (pytest, mypy, ruff, sphinx)
* The package in "editable" mode (changes reflect immediately)

Development Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~

The ``dev`` extra includes:

* **pytest** (>=8.4.2) - Testing framework
* **mypy** (>=1.18.2) - Type checking
* **ruff** (>=0.13.1) - Linting and formatting
* **sphinx** (>=8.2.3) - Documentation generation
* **sphinx-rtd-theme** (>=3.0.2) - Documentation theme

Virtual Environment Setup
--------------------------

It's recommended to use a virtual environment:

Using venv (Python 3.3+)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Create virtual environment
   python -m venv all2md-env

   # Activate it
   # On Windows:
   all2md-env\Scripts\activate

   # On macOS/Linux:
   source all2md-env/bin/activate

   # Install all2md
   pip install all2md[all]

   # Deactivate when done
   deactivate

Using conda
~~~~~~~~~~~

.. code-block:: bash

   # Create conda environment
   conda create -n all2md python=3.12
   conda activate all2md

   # Install all2md
   pip install all2md[all]

   # Deactivate when done
   conda deactivate

Verification
------------

Test your installation:

.. code-block:: python

   # Test basic functionality
   from all2md import to_markdown

   # Convert a simple text string
   result = to_markdown("# Hello World")
   print(result)  # Should print: # Hello World

   # Check version
   import all2md
   print(all2md.__version__)

Command Line Test
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Test CLI installation
   all2md --version

   # Test with stdin (Ctrl+C to exit)
   echo "# Test Document" | all2md

Common Installation Issues
--------------------------

Missing Dependencies
~~~~~~~~~~~~~~~~~~~~

**Error:** ``ImportError: No module named 'fitz'``

**Solution:** Install PDF support: ``pip install all2md[pdf]``

**Error:** ``ImportError: No module named 'docx'``

**Solution:** Install Word support: ``pip install all2md[docx]``

Python Version Issues
~~~~~~~~~~~~~~~~~~~~~

**Error:** ``ERROR: Package 'all2md' requires a different Python``

**Solution:** all2md requires Python 3.12+. Check your version:

.. code-block:: bash

   python --version

Install Python 3.12+ from https://python.org or use pyenv:

.. code-block:: bash

   # Install pyenv (macOS)
   brew install pyenv

   # Install Python 3.12
   pyenv install 3.12.0
   pyenv global 3.12.0

Permission Errors
~~~~~~~~~~~~~~~~~

**Error:** ``ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied``

**Solutions:**

1. Use a virtual environment (recommended):

   .. code-block:: bash

      python -m venv myenv
      source myenv/bin/activate  # On Windows: myenv\Scripts\activate
      pip install all2md[all]

2. Install for current user only:

   .. code-block:: bash

      pip install --user all2md[all]

Upgrade Installation
--------------------

To upgrade to the latest version:

.. code-block:: bash

   # Upgrade all2md and dependencies
   pip install --upgrade all2md[all]

   # Upgrade specific format dependencies
   pip install --upgrade all2md[pdf,docx]

Uninstall
---------

To completely remove all2md:

.. code-block:: bash

   pip uninstall all2md

   # Also remove optional dependencies if desired
   pip uninstall pymupdf python-docx python-pptx beautifulsoup4 pandas ebooklib odfpy pyth3 httpx

System-Specific Notes
---------------------

Windows
~~~~~~~

* Use Command Prompt or PowerShell
* Python launcher: ``py -m pip install all2md[all]``
* Some dependencies may require Microsoft Visual C++ Build Tools

macOS
~~~~~

* Use Terminal
* May need to install Xcode Command Line Tools: ``xcode-select --install``
* Consider using Homebrew for Python: ``brew install python@3.12``

Linux
~~~~~

* Use terminal/shell
* Some distributions may need development packages:

  .. code-block:: bash

     # Ubuntu/Debian
     sudo apt-get install python3-dev build-essential

     # CentOS/RHEL
     sudo yum install python3-devel gcc

Docker Installation
-------------------

Use all2md in a Docker container:

.. code-block:: dockerfile

   FROM python:3.12-slim

   # Install all2md with all dependencies
   RUN pip install all2md[all]

   # Optional: Set working directory
   WORKDIR /app

   # Optional: Copy your documents
   # COPY ./documents /app/documents

   CMD ["bash"]

Build and run:

.. code-block:: bash

   # Build image
   docker build -t all2md .

   # Run interactively
   docker run -it --rm -v $(pwd):/app all2md

   # Convert a document
   docker run --rm -v $(pwd):/app all2md all2md document.pdf

Next Steps
----------

Once installed:

1. Try the :doc:`quickstart` guide
2. Read the :doc:`overview` to understand the architecture
3. Explore :doc:`formats` for format-specific examples
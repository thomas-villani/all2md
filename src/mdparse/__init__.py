"""mdparse - A Python document conversion library for bidirectional transformation.

mdparse provides a comprehensive solution for converting between various file formats
and Markdown. It supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML),
Excel (XLSX), images, and 200+ text file formats with intelligent content extraction
and formatting preservation.

The library uses a modular architecture where the main `parse_file()` function
automatically detects file types and routes to appropriate specialized converters.
Each converter module handles specific format requirements while maintaining
consistent Markdown output with support for tables, images, and complex formatting.

Key Features
------------
- Bidirectional conversion (format-to-Markdown and Markdown-to-format)
- Advanced PDF parsing with table detection using PyMuPDF
- Word document processing with formatting preservation
- PowerPoint slide-by-slide extraction
- HTML processing with configurable conversion options
- Email chain parsing with attachment handling
- Base64 image embedding support
- Support for 200+ plaintext file formats

Supported Formats
-----------------
- **Documents**: PDF, DOCX, PPTX, HTML, EML
- **Spreadsheets**: XLSX, CSV, TSV
- **Images**: PNG, JPEG, GIF (embedded as base64)
- **Text**: 200+ formats including code files, configs, markup

Requirements
------------
- Python 3.12+
- Optional dependencies loaded per format (PyMuPDF, python-docx, etc.)

Examples
--------
Basic usage for file conversion:

    >>> from mdparse import parse_file
    >>> with open('document.pdf', 'rb') as f:
    ...     markdown_content = parse_file(f, 'document.pdf')
    >>> print(markdown_content)

With MIME type detection:

    >>> content, mimetype = parse_file(file_obj, filename, return_mimetype=True)
    >>> print(f"Detected type: {mimetype}")
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#
import base64
import mimetypes
import os
from io import BytesIO, StringIO
from typing import IO

PLAINTEXT_EXTENSIONS = [
    ".txt",  # Plain text file
    ".tsv",
    ".md",  # Markdown file
    ".json",  # JavaScript Object Notation file
    ".xml",  # Extensible Markup Language file
    ".html",  # Hypertext Markup Language file
    ".htm",
    ".css",  # Cascading Style Sheets file
    ".js",  # JavaScript file
    ".py",  # Python source code file
    ".java",  # Java source code file
    ".c",  # C source code file
    ".h",  # C source header file
    ".cs",  # C# source file
    ".cpp",  # C++ source code file
    ".hpp",  # C++ header file
    ".rb",  # Ruby source code file
    ".go",  # Go source code file
    ".php",  # PHP source code file
    ".sh",  # Shell script file
    ".pl",  # Perl script file
    ".sql",  # SQL database script file
    ".yaml",  # YAML Ain't Markup Language file
    ".toml",  # Tom's obvious markup language
    ".ini",  # Initialization file
    ".bat",  # Batch file
    ".r",  # R source code file
    ".swift",  # Swift source code file
    ".scala",  # Scala source code file
    ".ts",  # TypeScript file
    ".log",  # Log file
    ".properties",  # Java properties file
    ".kt",  # Kotlin source file
    ".kts",  # Kotlin script file
    ".rs",  # Rust source file
    ".lua",  # Lua source file
    ".ps1",  # PowerShell script
    ".vb",  # Visual Basic source file
    ".cmake",  # CMake build file
    ".gradle",  # Gradle build file
    ".groovy",  # Groovy source file
    ".dart",  # Dart source file
    ".elm",  # Elm source file
    ".ex",  # Elixir source file
    ".exs",  # Elixir script file
    ".fs",  # F# source file
    ".nim",  # Nim source file
    ".m",  # Objective-C source file
    ".mm",  # Objective-C++ source file
    ".rst",  # reStructuredText file
    ".jsx",  # React JavaScript XML file
    ".tsx",  # TypeScript XML file
    ".vue",  # Vue.js component file
    ".svelte",  # Svelte component file
    ".htm",  # Alternative HTML extension
    ".xhtml",  # Extensible HTML file
    ".tpl",  # Template file
    ".haml",  # HTML Abstraction Markup Language
    ".jade",  # Jade template file
    ".pug",  # Pug template file
    ".ejs",  # Embedded JavaScript template
    ".csv",  # Comma-separated values file
    ".clj",  # Clojure source file
    ".coffee",  # CoffeeScript source file
    ".hs",  # Haskell source file
    ".jl",  # Julia source file
    ".scm",  # Scheme source file
    ".lisp",  # Lisp source file
    ".asm",  # Assembly language source file
    ".erl",  # Erlang source file
    ".hrl",  # Erlang header file
    ".proto",  # Protocol Buffers file
    ".tf",  # Terraform configuration file
    ".cfg",  # Configuration file
    ".conf",  # Configuration file
    ".pyx",  # Cython source file
    ".sass",  # Sass stylesheet file
    ".scss",  # SCSS stylesheet file
    ".less",  # Less stylesheet file
    ".styl",  # Stylus stylesheet file
    ".hbs",  # Handlebars template file
    ".mustache",  # Mustache template file
    ".liquid",  # Liquid template file
    ".erb",  # ERB template file
    ".rake",  # Ruby Rake file
    ".gemspec",  # Ruby gem specification
    ".podspec",  # CocoaPods specification file
    ".pp",  # Puppet file
    ".env",  # Environment file
    ".graphql",  # GraphQL file
    ".gql",  # GraphQL file
    ".diff",  # Diff file
    ".patch",  # Patch file
    ".tex",  # LaTeX document file
    ".bib",  # BibTeX bibliography file
    ".adoc",  # AsciiDoc file
    ".textile",  # Textile markup file
    ".wiki",  # Wiki markup file
    ".mediawiki",  # MediaWiki markup file
    ".pod",  # Perl POD documentation
    ".rdoc",  # RDoc documentation
    ".org",  # Org-mode file
    ".markdown",  # Full Markdown file extension
    ".mdown",  # Alternative Markdown extension
    ".mkd",  # Alternative Markdown extension
    ".mkdn",  # Alternative Markdown extension
    ".mdwn",  # Alternative Markdown extension
    ".mdx",  # MDX Markdown file
    ".asciidoc",  # AsciiDoc file
    ".opml",  # OPML file
    ".rss",  # RSS feed
    ".atom",  # Atom feed
    ".ics",  # iCalendar file
    ".vcf",  # vCard file
    ".desktop",  # Linux desktop entry file
    ".plist",  # Property list file
    ".wsdl",  # Web Services Description Language file
    ".xsd",  # XML Schema Definition file
    ".dtd",  # Document Type Definition file
    ".jsonld",  # JSON-LD file
    ".json5",  # JSON5 file
    ".hjson",  # Hjson file
    ".cson",  # CoffeeScript Object Notation file
    ".geojson",  # GeoJSON file
    ".webmanifest",  # Web app manifest
    ".nfo",  # NFO file
    ".reg",  # Windows Registry file
    ".inf",  # Information file
    ".config",  # Configuration file
    ".xaml",  # XAML file
    ".sgml",  # SGML file
    ".bash",  # Bash script
    ".csh",  # C Shell script
    ".zsh",  # Z Shell script
    ".fish",  # Fish shell script
    ".ksh",  # Korn Shell script
    ".cmd",  # Windows Command script
    ".awk",  # AWK script
    ".sed",  # SED script
    ".vim",  # Vim script
    ".el",  # Emacs Lisp file
    ".svg",  # SVG file (XML-based)
    ".asp",  # Active Server Pages file
    ".aspx",  # ASP.NET file
    ".cshtml",  # Razor file
    ".vbhtml",  # Visual Basic Razor file
    ".rhtml",  # Ruby HTML file
    ".shtml",  # Server-parsed HTML file
    ".yml",  # Alternative YAML extension
    ".htaccess",  # Apache configuration file
    ".htpasswd",  # Apache password file
    ".d",  # D programming language source file
    ".f",  # Fortran source file
    ".f90",  # Fortran 90 source file
    ".f95",  # Fortran 95 source file
    ".for",  # Fortran source file
    ".pas",  # Pascal source file
    ".pro",  # Prolog source file
    ".tcl",  # Tcl script file
    ".thor",  # Thor script file
    ".sas",  # SAS program file
    ".v",  # Verilog source file
    ".vhd",  # VHDL source file
    ".make",  # Makefile
    ".mak",  # Alternative makefile
    ".jbuilder",  # JBuilder project file
    ".sbt",  # Scala build tool file
    ".cypher",  # Cypher query language file
    ".nsi",  # NSIS installer script
    ".nt",  # N-Triples file
    ".ttl",  # Turtle file
    ".p",  # Prolog source file
    ".gyp",  # GYP build file
    ".gn",  # GN build file
    ".bazel",  # Bazel build file
    ".eslintignore",  # ESLint ignore file
    ".prettierignore",  # Prettier ignore file
    ".bzl",  # Bazel rule file
    ".twig",  # Twig template file
    ".iml",  # IntelliJ module file
    ".nginx",  # Nginx configuration file
    ".mjs",  # JavaScript module file
    ".cjs",  # CommonJS module file
    ".wsgi",  # WSGI file
    ".prisma",  # Prisma schema file
    ".hcl",  # HashiCorp Configuration Language
    ".ipynb",  # Jupyter Notebook (JSON format)
    ".dockerfile",  # Docker configuration file
    ".jenkinsfile",  # Jenkins pipeline file
    ".eslintrc",  # ESLint configuration file
    ".babelrc",  # Babel configuration file
    ".stylelintrc",  # Stylelint configuration file
    ".editorconfig",  # EditorConfig file
    ".gitignore",  # Git ignore file
    ".gitattributes",  # Git attributes file
    ".npmrc",  # npm configuration file
    ".graphqlrc",  # GraphQL configuration file
    ".robots",  # Robots.txt file
    ".sitemap",  # Sitemap file
]

DOCUMENT_EXTENSIONS = [
    ".pdf",
    ".csv",
    ".xlsx",
    ".docx",
    ".pptx",
    ".eml",
]

IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
]

ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS


def parse_file(file: IO, filename: str, return_mimetype: bool = False) -> str | None | tuple[str | None, str | None]:
    """Parse the file and return the content as markdown (if possible) or None (if not)

    Parameters
    ----------
    file : IO
        A file-like object (e.g. BytesIO)
    filename : str
        Name needed for mimetype guessing
    return_mimetype : bool, default False
        If True, returns (content, mimetype)

    Returns
    -------
    str or None

    """

    _, extension = os.path.splitext(filename)
    is_dot_file = False
    # For dot-files
    if not extension and os.path.basename(filename).startswith("."):
        extension = os.path.basename(filename)
        is_dot_file = True

    extension = extension.lower()
    file_mimetype = mimetypes.guess_type(filename)[0]
    if file_mimetype is None:
        if extension in PLAINTEXT_EXTENSIONS:
            file_mimetype = "text/plain"
        if is_dot_file:
            file_mimetype = "text/plain"

    # Plain text
    if (file_mimetype and file_mimetype.startswith("text/")) or extension in PLAINTEXT_EXTENSIONS:
        file.seek(0)
        if extension in (".csv", ".tsv"):
            try:
                import pandas as pd

                df = pd.read_csv(file, delimiter="\t" if extension == "tsv" else ",", encoding="utf-8")
                content = df.to_markdown()
            except ImportError:
                content = file.read().decode("utf-8")

        else:
            content = file.read().decode("utf-8")
    # Excel file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "`pandas` is required to read xlsx files. Install with `pip install pandas`."
            ) from e

        excel_file = pd.ExcelFile(file)
        content = ""
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            content += "## " + sheet_name + "\n"
            content += df.to_markdown()
            content += "\n\n---\n\n"
    # Powerpoint file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        from .pptx2markdown import pptx_to_markdown

        file.seek(0)
        try:
            content = pptx_to_markdown(file)
        except ImportError as e:
            raise ImportError(
                "`python-pptx` is required to read powerpoint files. Install with `pip install python-pptx`."
            ) from e
    # Docx file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from .docx2markdown import docx_to_markdown

        file.seek(0)
        try:
            content = docx_to_markdown(file)
        except ImportError as e:
            raise ImportError(
                "`python-docx` is required to read Word docx files. Install with `pip install python-docx`."
            ) from e
    # PDF
    elif file_mimetype == "application/pdf":
        from .pdf2markdown import pdf_to_markdown

        file.seek(0)
        filestream = BytesIO(file.read())
        try:
            content = pdf_to_markdown(filestream)
        except ImportError as e:
            raise ImportError(
                "`pymupdf` version >1.24.0 is required to read PDF files. Install with `pip install pymupdf`"
            ) from e
    # Image
    elif file_mimetype and file_mimetype in ("image/png", "image/jpeg", "image/gif"):
        file.seek(0)
        b64_data = base64.b64encode(file.read()).decode("utf-8")
        content = f"data:{file_mimetype};base64,{b64_data}"
    # EML file (emails)
    elif file_mimetype == "message/rfc822":
        from .emlfile import parse_email_chain

        file.seek(0)
        eml_stream: StringIO = StringIO(file.read().decode("utf-8"))
        content = parse_email_chain(eml_stream, as_markdown=True)
    # Others
    else:  # elif file.content_type == "application/octet-stream":
        # guess = mimetypes.guess_type(file.filename)[0]
        # Try to just load it as text.
        file.seek(0)
        try:
            content = file.read().decode("utf-8")
        except UnicodeDecodeError:
            if return_mimetype:
                return (None, None)
            return None

    content = content.replace("\r\n", "\n")  # Fix windows newlines
    if return_mimetype:
        return content, file_mimetype
    return content


__all__ = [
    "ALL_ALLOWED_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "PLAINTEXT_EXTENSIONS",
    "parse_file",
]

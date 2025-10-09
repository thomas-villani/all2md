"""CHM test fixture generators for testing CHM-to-Markdown conversion.

This module provides functions to create mock CHM file objects for testing
CHM-to-Markdown conversion. Since pychm is a reading library and creating
real CHM files programmatically is complex, we use mocks for unit tests.

For integration tests, you may need to use real CHM files.
"""

from typing import Any, Optional
from unittest.mock import MagicMock


class MockCHMFile:
    """Mock CHM file object for testing.

    This class mimics the interface of chm.chm.CHMFile for testing purposes
    without requiring actual CHM files or the pychm library.

    Parameters
    ----------
    pages : dict[str, str]
        Dictionary mapping page paths to HTML content
    title : str, optional
        CHM file title
    home : str, optional
        Path to home page

    """

    def __init__(
        self,
        pages: dict[str, str] | None = None,
        title: str | None = None,
        home: str | None = None,
        topics: list[dict[str, Any]] | None = None
    ):
        """Initialize mock CHM file."""
        self.pages = pages or {}
        self.title = title
        self.home = home or (list(self.pages.keys())[0] if self.pages else None)
        self._topics = topics or []

    def LoadCHM(self, path: str) -> int:
        """Mock LoadCHM method.

        Parameters
        ----------
        path : str
            Path to CHM file

        Returns
        -------
        int
            1 for success, 0 for failure

        """
        return 1

    def ResolveObject(self, path: str) -> tuple[int, Any]:
        """Mock ResolveObject method.

        Parameters
        ----------
        path : str
            Path to object in CHM

        Returns
        -------
        tuple[int, Any]
            Status code and object reference

        """
        if path in self.pages:
            return (0, path)  # Success, return path as reference
        return (1, None)  # Failure

    def RetrieveObject(self, obj_ref: Any) -> tuple[int, bytes]:
        """Mock RetrieveObject method.

        Parameters
        ----------
        obj_ref : Any
            Object reference from ResolveObject

        Returns
        -------
        tuple[int, bytes]
            Status code and content bytes

        """
        if obj_ref in self.pages:
            content = self.pages[obj_ref]
            return (0, content.encode('utf-8'))
        return (1, b'')

    def GetTopicsTree(self) -> Optional[Any]:
        """Mock GetTopicsTree method.

        Returns
        -------
        Any or None
            Root node of topics tree or None

        """
        if not self._topics:
            return None
        return self._build_topic_node(self._topics)

    def _build_topic_node(self, topics: list[dict[str, Any]]) -> Any:
        """Build a topic tree node from topic data.

        Parameters
        ----------
        topics : list[dict[str, Any]]
            List of topic dictionaries

        Returns
        -------
        Any
            Mock topic node

        """
        if not topics:
            return None

        # Create root node
        root = MagicMock()
        root.title = topics[0].get('title', '')
        root.Local = topics[0].get('path', '')
        root.children = []

        # Add children
        for topic in topics[1:]:
            child = MagicMock()
            child.title = topic.get('title', '')
            child.Local = topic.get('path', '')
            child.children = []
            root.children.append(child)

        return root

    def Enumerate(self, flags: int, callback: Any, context: Any) -> int:
        """Mock Enumerate method.

        Parameters
        ----------
        flags : int
            Enumeration flags
        callback : callable
            Callback function
        context : Any
            Context object

        Returns
        -------
        int
            Status code

        """
        # Call callback for each page
        for path in self.pages.keys():
            ui = MagicMock()
            ui.path = path
            callback(self, ui, context)
        return 1


def create_simple_chm() -> MockCHMFile:
    """Create a simple mock CHM with basic structure for testing.

    Returns
    -------
    MockCHMFile
        Mock CHM file object

    """
    pages = {
        "/index.html": """
        <html>
            <head><title>Test CHM Document</title></head>
            <body>
                <h1>Welcome to Test CHM</h1>
                <p>This is the <strong>home page</strong> with <em>formatted text</em>.</p>
            </body>
        </html>
        """,
        "/chapter1.html": """
        <html>
            <body>
                <h1>Chapter 1: Introduction</h1>
                <p>This is the first chapter with <strong>bold text</strong> and <em>italic text</em>.</p>
                <p>This paragraph contains a <a href="https://example.com">link</a>.</p>
            </body>
        </html>
        """,
        "/chapter2.html": """
        <html>
            <body>
                <h1>Chapter 2: Content</h1>
                <p>This chapter has a list:</p>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                    <li>Item 3</li>
                </ul>
                <p>And a table:</p>
                <table>
                    <tr><th>Header 1</th><th>Header 2</th></tr>
                    <tr><td>Cell 1</td><td>Cell 2</td></tr>
                </table>
            </body>
        </html>
        """,
    }

    topics = [
        {"title": "Table of Contents", "path": "/index.html"},
        {"title": "Chapter 1: Introduction", "path": "/chapter1.html"},
        {"title": "Chapter 2: Content", "path": "/chapter2.html"},
    ]

    return MockCHMFile(
        pages=pages,
        title="Test CHM Document",
        home="/index.html",
        topics=topics
    )


def create_chm_with_nested_toc() -> MockCHMFile:
    """Create mock CHM with nested table of contents for testing.

    Returns
    -------
    MockCHMFile
        Mock CHM file object with nested TOC

    """
    pages = {
        "/index.html": "<html><body><h1>Main Page</h1></body></html>",
        "/part1/intro.html": "<html><body><h1>Part 1: Introduction</h1></body></html>",
        "/part1/details.html": "<html><body><h2>Details</h2></body></html>",
        "/part2/summary.html": "<html><body><h1>Part 2: Summary</h1></body></html>",
    }

    # Create nested topic structure
    root = MagicMock()
    root.title = "Main"
    root.Local = "/index.html"
    root.children = []

    part1 = MagicMock()
    part1.title = "Part 1: Introduction"
    part1.Local = "/part1/intro.html"
    part1.children = []

    part1_child = MagicMock()
    part1_child.title = "Details"
    part1_child.Local = "/part1/details.html"
    part1_child.children = []
    part1.children.append(part1_child)

    part2 = MagicMock()
    part2.title = "Part 2: Summary"
    part2.Local = "/part2/summary.html"
    part2.children = []

    root.children.extend([part1, part2])

    chm = MockCHMFile(pages=pages, title="Nested TOC Test", home="/index.html")
    chm._topics = [{"title": "Main", "path": "/index.html"}]
    # Override GetTopicsTree to return our custom structure
    chm.GetTopicsTree = lambda: root

    return chm


def create_chm_with_code() -> MockCHMFile:
    """Create mock CHM with code blocks for testing.

    Returns
    -------
    MockCHMFile
        Mock CHM file object with code content

    """
    pages = {
        "/index.html": """
        <html>
            <body>
                <h1>Code Examples</h1>
                <p>Python example:</p>
                <pre><code class="language-python">
def hello():
    print("Hello, World!")
                </code></pre>
                <p>JavaScript example:</p>
                <pre><code class="language-javascript">
function greet() {
    console.log("Hello!");
}
                </code></pre>
            </body>
        </html>
        """,
    }

    return MockCHMFile(
        pages=pages,
        title="Code Examples CHM",
        home="/index.html",
        topics=[{"title": "Code Examples", "path": "/index.html"}]
    )


def create_chm_with_images() -> MockCHMFile:
    """Create mock CHM with images for testing image handling.

    Returns
    -------
    MockCHMFile
        Mock CHM file object with images

    """
    pages = {
        "/index.html": """
        <html>
            <body>
                <h1>Document with Images</h1>
                <p>Here is an image:</p>
                <img src="images/test.png" alt="Test Image" />
                <p>And another with a title:</p>
                <img src="images/logo.png" alt="Logo" title="Company Logo" />
            </body>
        </html>
        """,
    }

    return MockCHMFile(
        pages=pages,
        title="Images Test CHM",
        home="/index.html",
        topics=[{"title": "Images", "path": "/index.html"}]
    )


def create_empty_chm() -> MockCHMFile:
    """Create empty mock CHM for testing edge cases.

    Returns
    -------
    MockCHMFile
        Empty mock CHM file object

    """
    return MockCHMFile(
        pages={},
        title="Empty CHM",
        home=None,
        topics=[]
    )

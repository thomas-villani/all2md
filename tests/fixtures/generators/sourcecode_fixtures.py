"""Source code fixture generators for language-specific parsing tests."""

from __future__ import annotations

from io import BytesIO
from textwrap import dedent


def create_python_module() -> str:
    """Return Python source that exercises docstrings, classes, and functions."""
    return dedent(
        """
        \"\"\"Example module used in conversion tests.\"\"\"

        from __future__ import annotations


        class Greeter:
            \"\"\"Simple greeter with configurable salutation.\"\"\"

            def __init__(self, salutation: str = "Hello") -> None:
                self.salutation = salutation

            def greet(self, name: str) -> str:
                return f"{self.salutation}, {name}!"


        def main() -> None:
            greeter = Greeter()
            print(greeter.greet("World"))


        if __name__ == "__main__":
            main()
        """
    ).lstrip()


def create_markdown_embedded_snippet() -> str:
    """Return source code that contains embedded markdown-style comments."""
    return dedent(
        """
        // Example demonstrating converter support for fenced comments.
        /*
        # Heading in comment

        - bullet item
        - another item
        */
        int add(int a, int b) {
            return a + b;
        }
        """
    ).lstrip()


def sourcecode_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode source code text to bytes."""
    return text.encode(encoding)


def sourcecode_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream for source code content."""
    return BytesIO(sourcecode_to_bytes(text, encoding=encoding))

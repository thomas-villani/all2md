"""Textile test fixture generators for testing Textile conversion.

This module provides functions to programmatically create Textile documents
for testing various aspects of Textile parsing and rendering.
"""

from io import BytesIO


def create_textile_with_formatting() -> str:
    """Create Textile with various text formatting for testing.

    Returns
    -------
    str
        Textile string with bold, italic, code, and other formatting.

    """
    textile = """h1. Formatting Test Document

h2. Basic Formatting

This paragraph contains *bold text*, _italic text_, and @inline code@.

This paragraph has *_bold and italic text_* combined.

h2. All Heading Levels

h3. Level 3 Heading

Content under level 3 heading.

h4. Level 4 Heading

Content under level 4 heading.

h5. Level 5 Heading

Content under level 5 heading.

h6. Level 6 Heading

Content under level 6 heading.

h2. Advanced Formatting

Text with ^superscript^ and ~subscript~.

Text with -strikethrough- content and +underline+ text.

h2. Block Quote

bq. This is a block quote with some important information.
It can span multiple lines and includes *bold* text.

h2. Horizontal Rule

<hr />

Content after horizontal rule.
"""
    return textile


def create_textile_with_lists() -> str:
    """Create Textile with various list structures for testing.

    Returns
    -------
    str
        Textile string with ordered, unordered, and nested lists.

    """
    textile = """h1. List Test Document

h2. Unordered List

* First item
* Second item
* Third item
** Nested item 1
** Nested item 2
* Fourth item

h2. Ordered List

# First item
# Second item
# Third item
## Nested ordered item 1
## Nested ordered item 2
# Fourth item

h2. Mixed Lists

# First ordered item
#* Nested unordered item
#* Another nested item
# Second ordered item
"""
    return textile


def create_textile_with_tables() -> str:
    """Create Textile with table structures for testing.

    Returns
    -------
    str
        Textile string with various table structures.

    """
    textile = """h1. Table Test Document

h2. Simple Table

|_.Name|_.Age|_.City|
|Alice Johnson|25|New York|
|Bob Smith|30|Los Angeles|
|Carol White|28|Chicago|

h2. Table with Inline Formatting

|_.Product|_.Status|_.Price|
|*Widget A*|_Available_|@$100@|
|*Widget B*|_Out of Stock_|@$150@|

h2. Table with Complex Content

|_.SKU|_.Name|_.Quantity|
|001|Widget A|50|
|002|Widget B|0|
|003|Widget C|25|
"""
    return textile


def create_textile_with_code_blocks() -> str:
    """Create Textile with code blocks for testing.

    Returns
    -------
    str
        Textile string with code blocks.

    """
    textile = """h1. Code Block Test Document

h2. Python Code

bc. def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
print(f"Result: {result}")

h2. JavaScript Code

bc. function greet(name) {
    console.log(`Hello, ${name}!`);
}

greet("World");

h2. Inline Code

Use @print()@ function to display output.

The @for@ loop iterates over items.
"""
    return textile


def create_textile_with_links_and_images() -> str:
    """Create Textile with links and images for testing.

    Returns
    -------
    str
        Textile string with links and images.

    """
    textile = """h1. Links and Images Test Document

h2. External Links

Visit "Example Website":https://www.example.com for more information.

You can also check out "Textile Documentation":https://textile-lang.com.

h2. Auto Links

Automatic link detection: https://www.google.com

Another auto link: http://github.com

h2. Images

!diagram.png(System Architecture Diagram)!

Inline image: !icon.png(Icon)! within text.

!photo.jpg(A beautiful landscape)!
"""
    return textile


def create_textile_complex_document() -> str:
    """Create a complex Textile document with multiple elements.

    Returns
    -------
    str
        Complex Textile string for comprehensive testing.

    """
    textile = """h1. Comprehensive Test Document

h2. Introduction

This document demonstrates *all* the _major_ features of @Textile@ formatting.
It includes ^superscript^ and ~subscript~ text.

Visit "our website":https://example.com for more information.

h2. Lists and Tables

h3. Shopping List

* Fruits
** Apples
** Bananas
** Oranges
* Vegetables
** Carrots
** Broccoli

h3. Product Comparison

|_.Feature|_.Product A|_.Product B|
|*Price*|$99|$149|
|_Warranty_|1 year|2 years|
|@Support@|Email|24/7 Phone|

h2. Code Examples

bc. class Calculator:
    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b

Use the @Calculator@ class for basic arithmetic.

h2. Important Information

bq. This is a critical note about the system.
It contains multiple paragraphs with *important* information
that users should read carefully.

h2. Visual Elements

!architecture.png(System Architecture)!

<hr />

h2. Conclusion

Thank you for reading this document.
"""
    return textile


def create_textile_with_nested_formatting() -> str:
    """Create Textile with nested formatting for edge case testing.

    Returns
    -------
    str
        Textile string with nested formatting.

    """
    textile = """h1. Nested Formatting Test

h2. Complex Nesting

This has *bold with _italic inside_ and more bold*.

This has _italic with *bold inside* and more italic_.

This has @code with special chars * and _ inside@.

h2. Lists with Formatting

* *Bold list item* with regular text
* _Italic list item_ with @inline code@
* List item with "formatted link":https://example.com

h2. Table with Nested Content

|_.Header 1|_.Header 2|
|Cell with *bold* and _italic_|Cell with @code@|
|Cell with "link":url|Cell with !icon.png(icon)!|

h2. Quote with Formatting

bq. This quote contains *bold*, _italic_, and @code@.
It also has special characters and formatting.
"""
    return textile


def create_simple_textile() -> str:
    """Create a simple Textile document for basic testing.

    Returns
    -------
    str
        Simple Textile string.

    """
    textile = """h1. Simple Document

This is a simple paragraph.

Another paragraph here.
"""
    return textile


def textile_bytes_io(textile_content: str) -> BytesIO:
    """Convert Textile string to BytesIO for testing.

    Parameters
    ----------
    textile_content : str
        Textile content as string

    Returns
    -------
    BytesIO
        BytesIO object containing UTF-8 encoded Textile

    """
    return BytesIO(textile_content.encode("utf-8"))

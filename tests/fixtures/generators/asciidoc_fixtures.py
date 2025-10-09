"""AsciiDoc test fixture generators for testing AsciiDoc conversion.

This module provides functions to programmatically create AsciiDoc documents
for testing various aspects of AsciiDoc parsing and rendering.
"""


def create_asciidoc_with_formatting() -> str:
    """Create AsciiDoc with various text formatting for testing.

    Returns
    -------
    str
        AsciiDoc string with bold, italic, code, and other formatting.

    """
    asciidoc = """= Formatting Test Document

== Basic Formatting

This paragraph contains *bold text*, _italic text_, and `inline code`.

This paragraph has *_bold and italic text_* combined.

== All Heading Levels

=== Level 3 Heading
Content under level 3 heading.

==== Level 4 Heading
Content under level 4 heading.

===== Level 5 Heading
Content under level 5 heading.

====== Level 6 Heading
Content under level 6 heading.

== Advanced Formatting

Text with ^superscript^ and ~subscript~.

Text with [line-through]#strikethrough# content.

== Block Quote

____
This is a block quote with some important information.
It can span multiple lines.
____

== Thematic Break

'''

Content after thematic break.
"""
    return asciidoc


def create_asciidoc_with_lists() -> str:
    """Create AsciiDoc with various list structures for testing.

    Returns
    -------
    str
        AsciiDoc string with ordered, unordered, and description lists.

    """
    asciidoc = """= List Test Document

== Unordered List

* First item
* Second item
* Third item
** Nested item 1
** Nested item 2
* Fourth item

== Ordered List

. First item
. Second item
. Third item
.. Nested ordered item 1
.. Nested ordered item 2
. Fourth item

== Checklist

* [x] Completed task
* [ ] Pending task
* [x] Another completed task

== Description List

CPU:: The brain of the computer
RAM:: Random Access Memory
GPU:: Graphics Processing Unit

== Mixed Lists

. First ordered item
* Nested unordered item
* Another nested item
. Second ordered item
"""
    return asciidoc


def create_asciidoc_with_tables() -> str:
    """Create AsciiDoc with table structures for testing.

    Returns
    -------
    str
        AsciiDoc string with various table structures.

    """
    asciidoc = """= Table Test Document

== Simple Table

|===
|Name |Age |City

|Alice Johnson
|25
|New York

|Bob Smith
|30
|Los Angeles

|Carol White
|28
|Chicago
|===

== Table with Inline Formatting

|===
|Product |Status |Price

|*Widget A*
|_Available_
|`$100`

|*Widget B*
|_Out of Stock_
|`$150`
|===

== Table with Caption

.Product Inventory
|===
|SKU |Name |Quantity

|001
|Widget A
|50

|002
|Widget B
|0
|===
"""
    return asciidoc


def create_asciidoc_with_code_blocks() -> str:
    """Create AsciiDoc with code blocks for testing.

    Returns
    -------
    str
        AsciiDoc string with code blocks.

    """
    asciidoc = """= Code Block Test Document

== Python Code

[source,python]
----
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
print(f"Result: {result}")
----

== JavaScript Code

[source,javascript]
----
function greet(name) {
    console.log(`Hello, ${name}!`);
}

greet("World");
----

== Plain Code Block

----
This is a plain code block
without language specification.
It preserves formatting.
    Including indentation.
----

== Inline Code

Use `print()` function to display output.

The `for` loop iterates over items.
"""
    return asciidoc


def create_asciidoc_with_links_and_images() -> str:
    """Create AsciiDoc with links and images for testing.

    Returns
    -------
    str
        AsciiDoc string with links and images.

    """
    asciidoc = """= Links and Images Test Document

== External Links

Visit link:https://www.example.com[Example Website] for more information.

You can also check out link:https://docs.asciidoctor.org[AsciiDoc Documentation].

== Auto Links

Automatic link detection: https://www.google.com

Another auto link: http://github.com

== Cross References

See <<section-a>> for details.

<<section-b,Click here>> to jump to section B.

[[section-a]]
== Section A

Content of section A.

[[section-b]]
== Section B

Content of section B.

== Images

image::diagram.png[System Architecture Diagram]

Inline image: image:icon.png[Icon] within text.

image::photo.jpg[A beautiful landscape,800,600]
"""
    return asciidoc


def create_asciidoc_with_attributes() -> str:
    """Create AsciiDoc with document attributes for testing.

    Returns
    -------
    str
        AsciiDoc string with various attributes.

    """
    asciidoc = """:title: Test Document with Attributes
:author: John Doe
:email: john.doe@example.com
:revdate: 2025-01-08
:description: A test document demonstrating AsciiDoc attributes
:keywords: testing, asciidoc, attributes
:lang: en
:custom-attribute: custom-value
:product-name: AwesomeProduct

= {title}

Document by {author} ({email})

== Product Information

Welcome to {product-name}!

This document was created on {revdate}.

== Attribute References

Custom attribute value: {custom-attribute}

Language: {lang}
"""
    return asciidoc


def create_asciidoc_complex_document() -> str:
    """Create a complex AsciiDoc document with multiple elements.

    Returns
    -------
    str
        Complex AsciiDoc string for comprehensive testing.

    """
    asciidoc = """:title: Comprehensive Test Document
:author: Test Author

= {title}

== Introduction

This document demonstrates *all* the _major_ features of `AsciiDoc` formatting.
It includes ^superscript^ and ~subscript~ text.

Visit link:https://example.com[our website] for more information.

== Lists and Tables

=== Shopping List

* Fruits
** Apples
** Bananas
** Oranges
* Vegetables
** Carrots
** Broccoli

=== Task List

* [x] Write documentation
* [x] Create tests
* [ ] Deploy application

=== Product Comparison

|===
|Feature |Product A |Product B

|*Price*
|$99
|$149

|_Warranty_
|1 year
|2 years

|`Support`
|Email
|24/7 Phone
|===

== Code Examples

[source,python]
----
class Calculator:
    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b
----

Use the `Calculator` class for basic arithmetic.

== Important Information

____
This is a critical note about the system.

It contains multiple paragraphs with *important* information
that users should read carefully.
____

== Visual Elements

image::architecture.png[System Architecture]

'''

== Conclusion

Thank you for reading this document.

For questions, contact {author}.
"""
    return asciidoc


def create_asciidoc_with_nested_formatting() -> str:
    """Create AsciiDoc with nested formatting for edge case testing.

    Returns
    -------
    str
        AsciiDoc string with nested formatting.

    """
    asciidoc = """= Nested Formatting Test

== Complex Nesting

This has *bold with _italic inside_ and more bold*.

This has _italic with *bold inside* and more italic_.

This has `code with special chars * and _ inside`.

== Lists with Formatting

* *Bold list item* with regular text
* _Italic list item_ with `inline code`
* List item with link:https://example.com[formatted link]

== Table with Nested Content

|===
|Header 1 |Header 2

|Cell with *bold* and _italic_
|Cell with `code`

|Cell with link:url[link]
|Cell with image:icon.png[icon]
|===

== Quote with Formatting

____
This quote contains *bold*, _italic_, and `code`.

It also has:

* A list item
* Another item

And a nested quote:

_____
Nested quote inside main quote
_____
____
"""
    return asciidoc


def create_simple_asciidoc() -> str:
    """Create a simple AsciiDoc document for basic testing.

    Returns
    -------
    str
        Simple AsciiDoc string.

    """
    asciidoc = """= Simple Document

This is a simple paragraph.

Another paragraph here.
"""
    return asciidoc

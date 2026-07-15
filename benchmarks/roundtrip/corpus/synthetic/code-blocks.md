A fenced code block with an info string:

```python
def hello(name):
    return f"hi {name}"
```

A fenced code block with no language:

```
plain preformatted text
  with indentation preserved
```

A fenced block that itself contains backticks, fenced with a longer run:

````markdown
```python
nested fence
```
````

A code block containing characters that look like markdown:

```
# not a heading
- not a list
*not emphasis*
| not | a table |
```

A code block nested inside a list item:

- here is some code:

  ```json
  {"key": "value"}
  ```

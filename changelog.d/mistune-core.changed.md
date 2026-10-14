- **A plain `pip install all2md` reads Markdown.** `mistune` moved from the `markdown`
  extra into the core dependencies, so `all2md README.md`, `all2md view` and
  `all2md read` work on a bare install. It is pure Python with no dependencies of its
  own. The `markdown` extra still exists, so `all2md[markdown]` install lines keep
  working. The quick start no longer claims the base install reads HTML and images.

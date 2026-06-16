#!/usr/bin/env bash
#
# llm-minify-pipe.sh -- shrink a document to token-lean text before sending it
# to an LLM. `all2md llm-minify` drops comments/frontmatter/raw HTML, replaces
# base64 images with short references, and collapses whitespace.
#
# Usage:
#   ./llm-minify-pipe.sh <document>
#
# Requires: all2md on PATH.
set -euo pipefail

DOC="${1:?Usage: llm-minify-pipe.sh <document>}"

# 1. Compact Markdown (default mode).
all2md llm-minify "$DOC" --out "minified.md"
echo "Wrote minified.md"

# 2. Compare sizes -- see how much you saved.
full=$(all2md "$DOC" | wc -w)
lean=$(all2md llm-minify "$DOC" | wc -w)
echo "Words: full=$full  minified=$lean"

# 3. Most aggressive: plain text, links/images/formatting stripped.
all2md llm-minify "$DOC" --aggressive --out "minified.txt"

# 4. Pipe straight into an LLM CLI. Replace `your-llm` with your tool of choice,
#    e.g. the Anthropic CLI, `llm`, etc.
#    all2md llm-minify "$DOC" | your-llm "Summarize the key points:"

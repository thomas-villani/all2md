# LLM Translation Example

This example demonstrates how to use all2md's AST transforms to translate documents using Large Language Models (LLMs) while preserving the original format and structure.

## Overview

The `llm_translation_demo.py` script shows how to:

1. **Parse** any supported document to AST (preserving structure)
2. **Transform** text nodes using an LLM (preserving formatting)
3. **Render** back to the original format (preserving layout)

This approach is **format-agnostic** - it works with PDF, DOCX, HTML, Markdown, and any other format supported by all2md.

## Why This Approach Works

Traditional document translation tools often:
- Lose formatting when converting to/from intermediate formats
- Can't handle complex layouts (tables, images, headings)
- Are format-specific (separate tools for PDF, DOCX, etc.)

The AST transform approach:
- ✅ Preserves all document structure
- ✅ Maintains formatting (bold, italic, headings, etc.)
- ✅ Works with any format
- ✅ Keeps tables, images, and metadata intact
- ✅ Translates only text, not code or URLs

## Installation

```bash
# Basic (with mock LLM)
# No additional dependencies needed

# With OpenAI
pip install openai
export OPENAI_API_KEY=your_key_here

# With Anthropic Claude
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

### Basic Example (Mock LLM)

```bash
# Demo translation (adds language prefix)
python examples/llm_translation_demo.py document.pdf translated.pdf --language Spanish
```

### With OpenAI

```bash
export OPENAI_API_KEY=your_key
python examples/llm_translation_demo.py report.docx report_es.docx --language Spanish --llm openai
```

### With Anthropic Claude

```bash
export ANTHROPIC_API_KEY=your_key
python examples/llm_translation_demo.py slides.pptx slides_fr.pptx --language French --llm anthropic
```

### Supported Formats

All formats supported by all2md work:

```bash
# PDF to PDF
python examples/llm_translation_demo.py doc.pdf doc_translated.pdf --language German

# DOCX to DOCX
python examples/llm_translation_demo.py doc.docx doc_translated.docx --language Italian

# HTML to HTML
python examples/llm_translation_demo.py page.html page_translated.html --language Portuguese

# Markdown to Markdown
python examples/llm_translation_demo.py readme.md readme_es.md --language Spanish

# SimpleDoc to SimpleDoc
python examples/llm_translation_demo.py data.sdoc data_fr.sdoc --language French
```

## How It Works

### 1. The Transform Class

```python
class LLMTranslateTransform(NodeTransformer):
    """Transform that translates text nodes using an LLM."""

    def visit_text(self, node: Text) -> Text:
        """Translate each text node."""
        translated = self.llm_client(node.content, self.target_language)
        return Text(content=translated, metadata=node.metadata.copy())
```

### 2. The Translation Pipeline

```python
# Parse document to AST
doc_ast = to_ast('document.pdf')

# Apply translation transform
translator = LLMTranslateTransform("Spanish", llm_client)
translated_ast = translator.transform(doc_ast)

# Render back to original format
from_ast(translated_ast, output_format='pdf', output_path='translated.pdf')
```

### 3. Smart Preservation

The transform automatically:
- **Preserves code blocks** (not translated)
- **Preserves URLs** (only link text translated)
- **Preserves structure** (headings, lists, tables)
- **Preserves formatting** (bold, italic, etc.)
- **Preserves metadata** (author, date, etc.)

## Custom LLM Integration

You can use any LLM by providing a translation function:

```python
def my_llm_translate(text: str, target_language: str) -> str:
    """Custom LLM translation function."""
    # Call your LLM API here
    response = my_llm_api.translate(text, target_language)
    return response.translated_text

translate_document(
    "input.pdf",
    "output.pdf",
    "Spanish",
    llm_client=my_llm_translate
)
```

### Example: Google Gemini

```python
def gemini_translate(text: str, target_language: str) -> str:
    """Translate using Google Gemini."""
    import google.generativeai as genai

    model = genai.GenerativeModel('gemini-pro')
    prompt = f"Translate to {target_language}: {text}"
    response = model.generate_content(prompt)
    return response.text
```

### Example: Local Ollama

```python
def ollama_translate(text: str, target_language: str) -> str:
    """Translate using local Ollama."""
    import requests

    response = requests.post('http://localhost:11434/api/generate', json={
        'model': 'llama2',
        'prompt': f'Translate to {target_language}: {text}'
    })
    return response.json()['response']
```

## Advanced Features

### Batch Translation

Translate multiple documents:

```python
import os

documents = ["doc1.pdf", "doc2.docx", "doc3.html"]
target_language = "French"

for doc in documents:
    base, ext = os.path.splitext(doc)
    output = f"{base}_fr{ext}"
    translate_document(doc, output, target_language)
```

### Custom Options

Control translation behavior:

```python
translator = LLMTranslateTransform(
    target_language="Spanish",
    llm_client=openai_translate,
    preserve_code=True,      # Don't translate code
    preserve_links=True       # Keep URLs unchanged
)
```

### Error Handling

The transform handles errors gracefully:

```python
def visit_text(self, node: Text) -> Text:
    try:
        translated = self.llm_client(node.content, self.target_language)
        return Text(content=translated)
    except Exception as e:
        # On error, keep original + add metadata
        metadata = node.metadata.copy()
        metadata['translation_error'] = str(e)
        return Text(content=node.content, metadata=metadata)
```

## Real-World Use Cases

### 1. Technical Documentation

Translate documentation while preserving:
- Code examples
- API references
- Table structures
- Image captions

```bash
python llm_translation_demo.py api_docs.md api_docs_es.md --language Spanish --llm openai
```

### 2. Business Reports

Translate reports while maintaining:
- Tables and charts
- Formatting (headers, footers)
- Page layout
- Company logos

```bash
python llm_translation_demo.py quarterly_report.pdf report_zh.pdf --language Chinese --llm anthropic
```

### 3. Academic Papers

Translate papers preserving:
- Citations
- Equations (MathML/LaTeX)
- Figures and tables
- Bibliography

```bash
python llm_translation_demo.py paper.docx paper_de.docx --language German --llm openai
```

### 4. Website Content

Translate HTML pages keeping:
- CSS classes
- HTML structure
- Navigation links
- Embedded media

```bash
python llm_translation_demo.py index.html index_fr.html --language French --llm anthropic
```

## Performance Considerations

### Cost Optimization

```python
# Cache translations to avoid duplicate LLM calls
class CachedLLMTranslate:
    def __init__(self, llm_client):
        self.cache = {}
        self.llm_client = llm_client

    def __call__(self, text, language):
        key = (text, language)
        if key not in self.cache:
            self.cache[key] = self.llm_client(text, language)
        return self.cache[key]

# Use cached translator
cached_client = CachedLLMTranslate(openai_translate)
translate_document("doc.pdf", "out.pdf", "Spanish", cached_client)
```

### Batch Processing

```python
# Collect all text first, then batch translate
class BatchLLMTranslate(NodeTransformer):
    def __init__(self, target_language, llm_client):
        super().__init__()
        self.target_language = target_language
        self.llm_client = llm_client
        self.texts_to_translate = []

    def visit_text(self, node: Text):
        self.texts_to_translate.append(node.content)
        return node

    def finalize(self):
        # Batch translate all collected texts
        translations = self.llm_client.batch_translate(
            self.texts_to_translate,
            self.target_language
        )
        # Apply translations...
```

## Testing

The example includes a mock LLM for testing without API calls:

```python
def mock_llm_translate(text: str, target_language: str) -> str:
    """Mock translation for testing."""
    return f"[{target_language.upper()}] {text}"
```

This is useful for:
- Testing the transform logic
- Verifying format preservation
- Demonstrating the workflow
- CI/CD pipelines

## Extending the Example

### Add Language Detection

```python
from langdetect import detect

def auto_detect_language(doc_ast: Document) -> str:
    """Detect source language from document."""
    sample_text = extract_sample_text(doc_ast)
    return detect(sample_text)
```

### Add Progress Tracking

```python
class ProgressLLMTranslate(LLMTranslateTransform):
    def __init__(self, *args, progress_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress_callback = progress_callback
        self.translated_count = 0

    def visit_text(self, node: Text):
        result = super().visit_text(node)
        self.translated_count += 1
        if self.progress_callback:
            self.progress_callback(self.translated_count)
        return result
```

### Add Glossary Support

```python
class GlossaryLLMTranslate(LLMTranslateTransform):
    def __init__(self, *args, glossary=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.glossary = glossary or {}

    def visit_text(self, node: Text):
        text = node.content
        # Replace glossary terms before LLM
        for term, translation in self.glossary.items():
            text = text.replace(term, translation)
        # Continue with LLM for rest...
```

## Troubleshooting

### Common Issues

1. **API Key Not Set**
   ```bash
   Error: OPENAI_API_KEY environment variable not set
   Solution: export OPENAI_API_KEY=your_key
   ```

2. **Rate Limiting**
   ```python
   # Add retry logic with exponential backoff
   import time

   def llm_with_retry(text, language, max_retries=3):
       for i in range(max_retries):
           try:
               return openai_translate(text, language)
           except RateLimitError:
               time.sleep(2 ** i)  # Exponential backoff
       raise
   ```

3. **Token Limits**
   ```python
   # Split long texts
   def split_text(text, max_tokens=1000):
       # Split at sentence boundaries
       sentences = text.split('. ')
       chunks = []
       current_chunk = []

       for sent in sentences:
           current_chunk.append(sent)
           if len(' '.join(current_chunk)) > max_tokens:
               chunks.append('. '.join(current_chunk[:-1]))
               current_chunk = [sent]

       if current_chunk:
           chunks.append('. '.join(current_chunk))

       return chunks
   ```

## License

This example is provided under the same license as all2md (MIT License).

## See Also

- [all2md AST Guide](../docs/source/ast_guide.rst)
- [all2md Transforms](../docs/source/transforms.rst)
- [Watermark Transform Example](./watermark-plugin)
- [SimpleDoc Parser Example](./simpledoc-plugin)

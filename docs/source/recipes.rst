Recipes and Cookbook
====================

This cookbook provides practical solutions to common, complex problems when using all2md. Each recipe demonstrates real-world scenarios with complete, tested examples that you can adapt to your needs.

For format-specific details, see :doc:`formats`. For configuration options, see :doc:`options`. For CLI batch processing, see :doc:`cli`. For AST manipulation, see :doc:`ast_guide`.

.. contents::
   :local:
   :depth: 2

Processing Mixed Document Collections
-------------------------------------

Converting Directory of Mixed Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** You have a directory with various document types (PDF, DOCX, PPTX, HTML) and need to convert them all to Markdown with consistent formatting.

**Solution:**

.. code-block:: bash

   # Create a configuration file for consistent settings
   cat > conversion_config.json << EOF
   {
       "attachment_mode": "download",
       "attachment_output_dir": "./extracted_media",
       "markdown.emphasis_symbol": "_",
       "markdown.bullet_symbols": "•◦▪",
       "extract_metadata": true,
       "pdf.detect_columns": true,
       "html.strip_dangerous_elements": true,
       "pptx.include_slide_numbers": true,
       "eml.convert_html_to_markdown": true
   }
   EOF

   # Convert all documents recursively with parallel processing
   all2md ./documents \
       --recursive \
       --parallel 4 \
       --output-dir ./markdown_output \
       --preserve-structure \
       --config conversion_config.json \
       --exclude "*.tmp" \
       --exclude "*.draft.*" \
       --skip-errors \
       --rich

**Python equivalent:**

.. code-block:: python

   import os
   from pathlib import Path
   from concurrent.futures import ThreadPoolExecutor
   from all2md import to_markdown, PdfOptions, HtmlOptions, PptxOptions, MarkdownRendererOptions

   def convert_documents_parallel(source_dir: str, output_dir: str):
       # Create shared markdown options
       md_options = MarkdownRendererOptions(
           emphasis_symbol="_",
           bullet_symbols="•◦▪",
           escape_special=False,
           use_hash_headings=True,
       )

       # Define format-specific options
       options_map = {
           'pdf': PdfOptions(
               attachment_mode="download",
               attachment_output_dir="./extracted_media",
               detect_columns=True,
           ),
           'html': HtmlOptions(
               attachment_mode="download",
               attachment_output_dir="./extracted_media",
               strip_dangerous_elements=True,
           ),
           'pptx': PptxOptions(
               attachment_mode="download",
               attachment_output_dir="./extracted_media",
               include_slide_numbers=True,
           )
       }

       def convert_file(file_path):
           try:
               # Get file extension to determine options
               ext = file_path.suffix.lower().lstrip('.')
               options = options_map.get(ext)

               # Convert to markdown
               markdown_content = to_markdown(
                   file_path,
                   parser_options=options,
                   renderer_options=md_options,
               )

               # Create output path preserving structure
               relative_path = file_path.relative_to(source_dir)
               output_path = Path(output_dir) / relative_path.with_suffix('.md')
               output_path.parent.mkdir(parents=True, exist_ok=True)

               # Write markdown file
               output_path.write_text(markdown_content, encoding='utf-8')
               print(f"Converted: {file_path} -> {output_path}")

           except Exception as e:
               print(f"Error converting {file_path}: {e}")

       # Find all supported files
       source_path = Path(source_dir)
       supported_extensions = {'.pdf', '.docx', '.pptx', '.html', '.eml', '.epub'}
       files = [f for f in source_path.rglob('*')
                if f.suffix.lower() in supported_extensions and f.is_file()]

       # Process in parallel
       with ThreadPoolExecutor(max_workers=4) as executor:
           executor.map(convert_file, files)

   # Usage
   convert_documents_parallel('./documents', './markdown_output')

Creating Text-Only Archive from Website
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Extract clean, text-only content from a collection of HTML files for archival or LLM training.

**Solution:**

.. code-block:: bash

   # Create configuration for clean text extraction
   cat > web_archive_config.json << EOF
   {
       "attachment_mode": "skip",
       "html.extract_title": true,
       "html.strip_dangerous_elements": true,
       "html.convert_nbsp": true,
       "markdown.escape_special": false,
       "markdown.use_hash_headings": true
   }
   EOF

   # Process HTML files and combine into archive
   all2md ./website_files/*.html \
       --config web_archive_config.json \
       --collate \
       --out website_archive.md

**Python solution with metadata preservation:**

.. code-block:: python

   from pathlib import Path
   from datetime import datetime
   from all2md import to_markdown, HtmlOptions, MarkdownRendererOptions

   def create_website_archive(html_dir: str, output_file: str):
       md_options = MarkdownRendererOptions(
           escape_special=False,  # Keep text readable
           use_hash_headings=True
       )

       html_options = HtmlOptions(
           attachment_mode="skip",
           extract_title=True,
           strip_dangerous_elements=True,
           convert_nbsp=True,
       )

       html_files = list(Path(html_dir).glob('*.html'))
       archive_content = []

       # Add archive header
       archive_content.append(f"""# Website Archive
   Generated on: {datetime.now().isoformat()}
   Total pages: {len(html_files)}
   Source directory: {html_dir}

   """)

       for i, html_file in enumerate(html_files, 1):
           try:
               # Convert HTML to markdown
               markdown = to_markdown(
                   html_file,
                   parser_options=html_options,
                   renderer_options=md_options,
               )

               # Add page separator with metadata
               separator = "=" * 80
               header = f"\\n{separator}\\nPage {i}: {html_file.name}\\n{separator}\\n\\n"

               archive_content.append(header + markdown)
               print(f"Processed: {html_file.name}")

           except Exception as e:
               print(f"Error processing {html_file}: {e}")
               continue

       # Write combined archive
       Path(output_file).write_text('\\n\\n'.join(archive_content), encoding='utf-8')
       print(f"Archive created: {output_file}")

   # Usage
   create_website_archive('./scraped_website', 'company_website_archive.md')

LLM Training Data Pipeline
--------------------------

Document Processing for Fine-tuning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Process a large collection of technical documents (PDFs, DOCX) to create clean training data for LLM fine-tuning.

**Solution:**

.. code-block:: python

   import json
   from pathlib import Path
   from typing import Dict, List
   from all2md import to_markdown, PdfOptions, DocxOptions, MarkdownRendererOptions

   class LLMDataProcessor:
       def __init__(self, output_dir: str):
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(exist_ok=True)

           # Configure for clean, minimal markdown
           self.md_options = MarkdownRendererOptions(
               escape_special=False,  # Don't escape for readability
               emphasis_symbol="*",
               bullet_symbols="*-+",
               use_hash_headings=True,
           )

           self.pdf_options = PdfOptions(
               attachment_mode="skip",  # No images in training data
               extract_metadata=True,
               detect_columns=True,
               merge_hyphenated_words=True,
               enable_table_fallback_detection=True,
           )

           self.docx_options = DocxOptions(
               attachment_mode="skip",
               preserve_tables=True,
               extract_metadata=True,
           )

       def process_document(self, file_path: Path) -> Dict:
           """Process a single document and return metadata + content."""
           try:
               # Determine options based on file type
               if file_path.suffix.lower() == '.pdf':
                   options = self.pdf_options
               elif file_path.suffix.lower() == '.docx':
                   options = self.docx_options
               else:
                   options = None

               # Convert to markdown
               content = to_markdown(
                   file_path,
                   parser_options=options,
                   renderer_options=self.md_options,
               )

               # Clean up content for training
               content = self.clean_content(content)

               # Create metadata
               metadata = {
                   "source_file": str(file_path),
                   "file_type": file_path.suffix.lower(),
                   "content_length": len(content),
                   "word_count": len(content.split()),
                   "has_tables": "| " in content,
                   "has_code": "```" in content or "`" in content
               }

               return {"metadata": metadata, "content": content}

           except Exception as e:
               print(f"Error processing {file_path}: {e}")
               return None

       def clean_content(self, content: str) -> str:
           """Clean content for LLM training."""
           # Remove excessive whitespace
           lines = [line.strip() for line in content.split('\\n')]
           lines = [line for line in lines if line]  # Remove empty lines

           # Rejoin with single newlines
           content = '\\n'.join(lines)

           # Remove multiple consecutive newlines
           while '\\n\\n\\n' in content:
               content = content.replace('\\n\\n\\n', '\\n\\n')

           return content

       def process_collection(self, source_dirs: List[str]) -> None:
           """Process entire document collection."""
           all_data = []
           supported_exts = {'.pdf', '.docx'}

           for source_dir in source_dirs:
               source_path = Path(source_dir)
               files = [f for f in source_path.rglob('*')
                       if f.suffix.lower() in supported_exts and f.is_file()]

               for file_path in files:
                   result = self.process_document(file_path)
                   if result:
                       all_data.append(result)

           # Save in JSONL format for training
           output_file = self.output_dir / "training_data.jsonl"
           with output_file.open('w', encoding='utf-8') as f:
               for item in all_data:
                   json.dump(item, f, ensure_ascii=False)
                   f.write('\\n')

           # Save summary statistics
           stats = {
               "total_documents": len(all_data),
               "total_words": sum(item["metadata"]["word_count"] for item in all_data),
               "file_types": {},
               "documents_with_tables": sum(1 for item in all_data if item["metadata"]["has_tables"]),
               "documents_with_code": sum(1 for item in all_data if item["metadata"]["has_code"])
           }

           for item in all_data:
               file_type = item["metadata"]["file_type"]
               stats["file_types"][file_type] = stats["file_types"].get(file_type, 0) + 1

           with (self.output_dir / "processing_stats.json").open('w') as f:
               json.dump(stats, f, indent=2)

           print(f"Processed {len(all_data)} documents")
           print(f"Total words: {stats['total_words']:,}")
           print(f"Output saved to: {output_file}")

   # Usage
   processor = LLMDataProcessor("./training_data_output")
   processor.process_collection(["./technical_docs", "./manuals", "./reports"])

Secure Document Processing
--------------------------

Web Application Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Safely process user-uploaded documents in a web application with strict security controls.

**Solution:**

.. code-block:: python

   import tempfile
   import os
   from pathlib import Path
   from typing import Optional, Union
   from all2md import to_markdown, HtmlOptions, PdfOptions, MarkdownRendererOptions
   from all2md.options import NetworkFetchOptions, LocalFileAccessOptions

   class SecureDocumentProcessor:
       """Secure document processor for web applications."""

       def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB default
           self.max_file_size = max_file_size

           # Security-focused markdown options
           self.md_options = MarkdownRendererOptions(
               escape_special=True,  # Escape for security
               use_hash_headings=True
           )

           # Secure PDF processing
           self.pdf_options = PdfOptions(
               attachment_mode="skip",  # No file downloads in web context
               extract_metadata=False,  # Avoid potential metadata exploits
            )

           # Secure HTML processing
           self.html_options = HtmlOptions(
               attachment_mode="skip",
               network=NetworkFetchOptions(
                   allow_remote_fetch=False,  # Prevent SSRF attacks
                   require_https=True,
                   network_timeout=5.0,
                ),
               local_files=LocalFileAccessOptions(
                   allow_local_files=False   # Prevent local file access
               ),
               strip_dangerous_elements=True,  # Remove scripts/styles
               max_asset_size_bytes=1024 * 1024,
            )

       def validate_file(self, file_data: bytes, filename: str) -> bool:
           """Validate uploaded file before processing."""
           # Check file size
           if len(file_data) > self.max_file_size:
               raise ValueError(f"File too large: {len(file_data)} bytes")

           # Check file extension
           allowed_extensions = {'.pdf', '.docx', '.html', '.txt'}
           ext = Path(filename).suffix.lower()
           if ext not in allowed_extensions:
               raise ValueError(f"Unsupported file type: {ext}")

           # Basic content validation
           if len(file_data) < 10:
               raise ValueError("File appears to be empty or corrupted")

           return True

       def process_upload(self, file_data: bytes, filename: str) -> dict:
           """Safely process uploaded file."""
           try:
               # Validate input
               self.validate_file(file_data, filename)

               # Determine file type and options
               ext = Path(filename).suffix.lower()
               if ext == '.pdf':
                   options = self.pdf_options
               elif ext == '.html':
                   options = self.html_options
               else:
                   options = None

               # Process in temporary file for security
               with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                   temp_file.write(file_data)
                   temp_file.flush()

                   try:
                       # Convert to markdown
                       markdown_content = to_markdown(
                           temp_file.name,
                           parser_options=options,
                           renderer_options=self.md_options,
                       )

                       # Limit output size (prevent DoS)
                       max_output = 1024 * 1024  # 1MB markdown limit
                       if len(markdown_content) > max_output:
                           markdown_content = markdown_content[:max_output] + "\\n\\n[Content truncated for size limit]"

                       return {
                           "success": True,
                           "content": markdown_content,
                           "filename": filename,
                           "file_type": ext,
                           "content_length": len(markdown_content)
                       }

                   finally:
                       # Clean up temp file
                       os.unlink(temp_file.name)

           except Exception as e:
               return {
                   "success": False,
                   "error": str(e),
                   "filename": filename
               }

   # Flask integration example
   from flask import Flask, request, jsonify

   app = Flask(__name__)
   processor = SecureDocumentProcessor()

   @app.route('/convert', methods=['POST'])
   def convert_document():
       if 'file' not in request.files:
           return jsonify({"error": "No file provided"}), 400

       file = request.files['file']
       if file.filename == '':
           return jsonify({"error": "No file selected"}), 400

       # Process the uploaded file
       file_data = file.read()
       result = processor.process_upload(file_data, file.filename)

       if result["success"]:
           return jsonify({
               "markdown": result["content"],
               "metadata": {
                   "filename": result["filename"],
                   "file_type": result["file_type"],
                   "content_length": result["content_length"]
               }
           })
       else:
           return jsonify({"error": result["error"]}), 400

Advanced Batch Processing
-------------------------

Directory Processing with Progress Tracking
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Process thousands of documents with detailed progress tracking and error reporting.

**Solution:**

.. code-block:: python

   import json
   import time
   from pathlib import Path
   from concurrent.futures import ThreadPoolExecutor, as_completed
   from dataclasses import dataclass, asdict
   from typing import List, Dict, Optional
   from all2md import to_markdown, PdfOptions, DocxOptions, MarkdownRendererOptions

   @dataclass
   class ProcessingResult:
       file_path: str
       success: bool
       output_path: Optional[str] = None
       error: Optional[str] = None
       processing_time: float = 0.0
       content_length: int = 0
       word_count: int = 0

   class BatchProcessor:
       """Advanced batch processor with progress tracking."""

       def __init__(self, output_dir: str, max_workers: int = 4):
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(parents=True, exist_ok=True)
           self.max_workers = max_workers

           # Setup options
           self.md_options = MarkdownRendererOptions(
               emphasis_symbol="_",
               use_hash_headings=True
           )

           self.options_map = {
               '.pdf': PdfOptions(
                   attachment_mode="download",
                   attachment_output_dir=str(self.output_dir / "media"),
               ),
               '.docx': DocxOptions(
                   attachment_mode="download",
                   attachment_output_dir=str(self.output_dir / "media"),
               )
           }

       def process_file(self, file_path: Path) -> ProcessingResult:
           """Process a single file with timing and error handling."""
           start_time = time.time()

           try:
               # Get appropriate options
               ext = file_path.suffix.lower()
               options = self.options_map.get(ext)

               # Convert to markdown
               content = to_markdown(
                   file_path,
                   parser_options=options,
                   renderer_options=self.md_options,
               )

               # Create output path
               relative_path = file_path.relative_to(file_path.parent)
               output_path = self.output_dir / relative_path.with_suffix('.md')
               output_path.parent.mkdir(parents=True, exist_ok=True)

               # Write output
               output_path.write_text(content, encoding='utf-8')

               processing_time = time.time() - start_time
               word_count = len(content.split())

               return ProcessingResult(
                   file_path=str(file_path),
                   success=True,
                   output_path=str(output_path),
                   processing_time=processing_time,
                   content_length=len(content),
                   word_count=word_count
               )

           except Exception as e:
               processing_time = time.time() - start_time
               return ProcessingResult(
                   file_path=str(file_path),
                   success=False,
                   error=str(e),
                   processing_time=processing_time
               )

       def process_batch(self, input_paths: List[Path],
                        progress_callback=None) -> List[ProcessingResult]:
           """Process multiple files with progress tracking."""
           results = []
           completed = 0
           total = len(input_paths)

           with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
               # Submit all tasks
               future_to_path = {
                   executor.submit(self.process_file, path): path
                   for path in input_paths
               }

               # Process completed tasks
               for future in as_completed(future_to_path):
                   result = future.result()
                   results.append(result)
                   completed += 1

                   # Progress callback
                   if progress_callback:
                       progress_callback(completed, total, result)

                   # Simple progress logging
                   status = "✓" if result.success else "✗"
                   print(f"{status} [{completed:4d}/{total:4d}] {Path(result.file_path).name}")

           return results

       def generate_report(self, results: List[ProcessingResult]) -> Dict:
           """Generate processing report."""
           successful = [r for r in results if r.success]
           failed = [r for r in results if not r.success]

           report = {
               "summary": {
                   "total_files": len(results),
                   "successful": len(successful),
                   "failed": len(failed),
                   "success_rate": len(successful) / len(results) * 100 if results else 0,
                   "total_processing_time": sum(r.processing_time for r in results),
                   "total_words": sum(r.word_count for r in successful),
                   "average_processing_time": sum(r.processing_time for r in results) / len(results) if results else 0
               },
               "successful_files": [asdict(r) for r in successful],
               "failed_files": [asdict(r) for r in failed]
           }

           return report

   # Usage example with progress tracking
   def process_documents_with_progress():
       processor = BatchProcessor("./converted_docs", max_workers=6)

       # Find all files to process
       input_dir = Path("./source_documents")
       file_patterns = ["*.pdf", "*.docx"]
       input_files = []

       for pattern in file_patterns:
           input_files.extend(input_dir.rglob(pattern))

       print(f"Found {len(input_files)} files to process")

       # Custom progress callback
       def progress_callback(completed, total, result):
           if result.success:
               print(f"  → Converted {result.word_count:,} words in {result.processing_time:.2f}s")
           else:
               print(f"  → Error: {result.error}")

       # Process files
       results = processor.process_batch(input_files, progress_callback)

       # Generate and save report
       report = processor.generate_report(results)
       report_path = Path("./converted_docs/processing_report.json")
       report_path.write_text(json.dumps(report, indent=2))

       # Print summary
       summary = report["summary"]
       print(f"\\nProcessing Complete:")
       print(f"  Files processed: {summary['total_files']}")
       print(f"  Successful: {summary['successful']} ({summary['success_rate']:.1f}%)")
       print(f"  Failed: {summary['failed']}")
       print(f"  Total words: {summary['total_words']:,}")
       print(f"  Total time: {summary['total_processing_time']:.2f}s")
       print(f"  Report saved: {report_path}")

   # Run the batch processing
   process_documents_with_progress()

Real-Time Progress Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Need detailed, real-time progress updates during long-running PDF conversions with table detection.

**Solution:**

Use the built-in progress callback system for fine-grained progress tracking:

.. code-block:: python

   from all2md import to_markdown, ProgressEvent
   import time

   class ProgressMonitor:
       """Monitor conversion progress with detailed statistics."""

       def __init__(self):
           self.start_time = None
           self.pages_processed = 0
           self.tables_found = 0

       def callback(self, event: ProgressEvent):
           """Handle progress events from all2md."""
           if event.event_type == "started":
               self.start_time = time.time()
               print(f"Starting: {event.message} (Total: {event.total} pages)")

            elif event.event_type == "item_done" and event.metadata.get("item_type") == "page":
                self.pages_processed += 1
                elapsed = time.time() - self.start_time
                pct = event.current / event.total * 100 if event.total > 0 else 0
                print(f"  Page {event.current}/{event.total} ({pct:.1f}%)")

            elif event.event_type == "detected" and event.metadata.get('detected_type') == 'table':
                count = event.metadata.get('table_count', 0)
                self.tables_found += count
                print(f"  Found {count} table(s) on page {event.current}")

           elif event.event_type == "finished":
               elapsed = time.time() - self.start_time
               print(f"Complete! ({elapsed:.2f}s, {self.tables_found} tables total)")

   # Use the monitor
   monitor = ProgressMonitor()
   markdown = to_markdown("document.pdf", progress_callback=monitor.callback)

**GUI Integration Example:**

.. code-block:: python

   import tkinter as tk
   from tkinter import ttk
   from all2md import to_markdown, ProgressEvent
   import threading

   class ConverterGUI:
       def __init__(self, root):
           self.progress = ttk.Progressbar(root, length=400, mode='determinate')
           self.progress.pack(pady=20)
           self.status = tk.Label(root, text="Ready")
           self.status.pack()

       def progress_callback(self, event: ProgressEvent):
           if event.total > 0:
               self.progress['value'] = (event.current / event.total) * 100
           self.status['text'] = event.message
           self.root.update_idletasks()

       def convert(self, filepath):
           threading.Thread(
               target=lambda: to_markdown(filepath, progress_callback=self.progress_callback),
               daemon=True
           ).start()

Complex Format Combinations
---------------------------

Email Chain Analysis
~~~~~~~~~~~~~~~~~~~~

**Problem:** Process email threads (.eml files) and extract structured information for analysis.

**Solution:**

.. code-block:: python

   import re
   from pathlib import Path
   from datetime import datetime
   from typing import List, Dict, Optional
   from all2md import to_markdown, EmlOptions, MarkdownRendererOptions

   class EmailAnalyzer:
       """Advanced email processing and analysis."""

       def __init__(self):
           self.md_options = MarkdownRendererOptions(
               use_hash_headings=True,
               escape_special=False,  # Keep email content readable
           )

           self.eml_options = EmlOptions(
               include_headers=True,
               preserve_thread_structure=True,
               convert_html_to_markdown=True,
               clean_quotes=True,
               detect_reply_separators=True,
               clean_wrapped_urls=True,
               date_format_mode="iso8601",
           )

       def extract_email_metadata(self, markdown_content: str) -> Dict:
           """Extract structured metadata from email markdown."""
           metadata = {
               "participants": set(),
               "date_range": {"earliest": None, "latest": None},
               "subject": None,
               "reply_count": 0,
               "has_attachments": False,
               "thread_depth": 0
           }

           # Extract email addresses
           email_pattern = r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b'
           emails = re.findall(email_pattern, markdown_content, re.IGNORECASE)
           metadata["participants"] = set(emails)

           # Extract dates
           date_pattern = r'Date: ([0-9T:-]+)'
           dates = re.findall(date_pattern, markdown_content)
           if dates:
               parsed_dates = []
               for date_str in dates:
                   try:
                       parsed_dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')))
                   except:
                       continue

               if parsed_dates:
                   metadata["date_range"]["earliest"] = min(parsed_dates)
                   metadata["date_range"]["latest"] = max(parsed_dates)

           # Count reply indicators
           metadata["reply_count"] = markdown_content.count("Re:")

           # Check for attachments
           metadata["has_attachments"] = "attachment" in markdown_content.lower()

           # Estimate thread depth by indentation/quote levels
           quote_levels = [line.count('>') for line in markdown_content.split('\\n') if line.strip().startswith('>')]
           metadata["thread_depth"] = max(quote_levels) if quote_levels else 0

           return metadata

       def process_email_collection(self, email_dir: Path) -> Dict:
           """Process a collection of email files."""
           results = {
               "emails": [],
               "summary": {
                   "total_emails": 0,
                   "total_participants": set(),
                   "date_range": {"earliest": None, "latest": None},
                   "threads_by_subject": {},
                   "top_participants": {},
                   "attachment_count": 0
               }
           }

           eml_files = list(email_dir.glob("*.eml"))

           for eml_file in eml_files:
               try:
                   # Convert email to markdown
                   markdown_content = to_markdown(
                       eml_file,
                       parser_options=self.eml_options,
                       renderer_options=self.md_options,
                   )

                   # Extract metadata
                   metadata = self.extract_email_metadata(markdown_content)

                   # Save processed email
                   email_result = {
                       "file_path": str(eml_file),
                       "content": markdown_content,
                       "metadata": metadata
                   }
                   results["emails"].append(email_result)

                   # Update summary statistics
                   results["summary"]["total_emails"] += 1
                   results["summary"]["total_participants"].update(metadata["participants"])

                   # Update date range
                   if metadata["date_range"]["earliest"]:
                       if not results["summary"]["date_range"]["earliest"]:
                           results["summary"]["date_range"]["earliest"] = metadata["date_range"]["earliest"]
                       else:
                           results["summary"]["date_range"]["earliest"] = min(
                               results["summary"]["date_range"]["earliest"],
                               metadata["date_range"]["earliest"]
                           )

                   # Count attachments
                   if metadata["has_attachments"]:
                       results["summary"]["attachment_count"] += 1

                   print(f"Processed: {eml_file.name}")

               except Exception as e:
                   print(f"Error processing {eml_file}: {e}")

           # Generate participant frequency
           for email in results["emails"]:
               for participant in email["metadata"]["participants"]:
                   results["summary"]["top_participants"][participant] = \\
                       results["summary"]["top_participants"].get(participant, 0) + 1

           # Convert sets to lists for JSON serialization
           results["summary"]["total_participants"] = list(results["summary"]["total_participants"])

           return results

       def create_analysis_report(self, analysis_results: Dict, output_dir: Path) -> None:
           """Create comprehensive analysis report."""
           output_dir.mkdir(parents=True, exist_ok=True)

           # Create main report markdown
           report_content = f"""# Email Collection Analysis Report

   ## Summary
   - **Total Emails**: {analysis_results['summary']['total_emails']}
   - **Unique Participants**: {len(analysis_results['summary']['total_participants'])}
   - **Emails with Attachments**: {analysis_results['summary']['attachment_count']}
   - **Date Range**: {analysis_results['summary']['date_range']['earliest']} to {analysis_results['summary']['date_range']['latest']}

   ## Top Participants
   """

           # Add participant statistics
           top_participants = sorted(
               analysis_results['summary']['top_participants'].items(),
               key=lambda x: x[1],
               reverse=True
           )[:10]

           for email, count in top_participants:
               report_content += f"- **{email}**: {count} emails\\n"

           report_content += "\\n## Individual Emails\\n\\n"

           # Add each email with summary
           for i, email in enumerate(analysis_results['emails'], 1):
               metadata = email['metadata']
               report_content += f"""### Email {i}: {Path(email['file_path']).name}
   - **Participants**: {len(metadata['participants'])}
   - **Thread Depth**: {metadata['thread_depth']}
   - **Has Attachments**: {metadata['has_attachments']}
   - **Reply Count**: {metadata['reply_count']}

   {email['content']}

   ---

   """

           # Save report
           (output_dir / "email_analysis_report.md").write_text(report_content)

           # Save raw data as JSON
           import json
           json_data = analysis_results.copy()
           # Convert datetime objects for JSON serialization
           for email in json_data['emails']:
               meta = email['metadata']
               if meta['date_range']['earliest']:
                   meta['date_range']['earliest'] = meta['date_range']['earliest'].isoformat()
               if meta['date_range']['latest']:
                   meta['date_range']['latest'] = meta['date_range']['latest'].isoformat()
               meta['participants'] = list(meta['participants'])

           if json_data['summary']['date_range']['earliest']:
               json_data['summary']['date_range']['earliest'] = json_data['summary']['date_range']['earliest'].isoformat()
           if json_data['summary']['date_range']['latest']:
               json_data['summary']['date_range']['latest'] = json_data['summary']['date_range']['latest'].isoformat()

           (output_dir / "email_analysis_data.json").write_text(
               json.dumps(json_data, indent=2, default=str)
           )

   # Usage
   analyzer = EmailAnalyzer()
   email_dir = Path("./email_collection")
   results = analyzer.process_email_collection(email_dir)
   analyzer.create_analysis_report(results, Path("./email_analysis_output"))

Security-Focused Workflows
---------------------------

Secure Web Scraping and Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Download and convert web pages securely while protecting against SSRF attacks and malicious content.

**Solution:**

.. code-block:: python

   import requests
   from pathlib import Path
   from all2md import to_markdown, HtmlOptions
   from all2md.options import NetworkFetchOptions, LocalFileAccessOptions

   class SecureWebScraper:
       """Secure web page scraper with SSRF protection."""

       def __init__(self, output_dir: str):
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(parents=True, exist_ok=True)

           # Configure strict security options
           self.html_options = HtmlOptions(
               strip_dangerous_elements=True,
               extract_title=True,
               network=NetworkFetchOptions(
                   allow_remote_fetch=True,
                   # Only allow images from trusted CDNs
                   allowed_hosts=[
                       "cdn.jsdelivr.net",
                       "unpkg.com",
                       "images.unsplash.com"
                   ],
                   require_https=True,
                   network_timeout=10.0,
                   max_remote_asset_bytes=5*1024*1024  # 5MB limit
               ),
               local_files=LocalFileAccessOptions(
                   allow_local_files=False,  # Block file:// URLs
                   allow_cwd_files=False
               ),
               attachment_mode='download',
               attachment_output_dir=str(self.output_dir / 'images')
           )

       def scrape_url(self, url: str, output_filename: str) -> dict:
           """Safely scrape and convert a web page."""
           try:
               # Validate URL (basic check)
               if not url.startswith(('https://', 'http://')):
                   raise ValueError("Only HTTP(S) URLs allowed")

               # Fetch with timeout
               response = requests.get(
                   url,
                   timeout=30,
                   headers={'User-Agent': 'all2md-scraper/1.0'},
                   allow_redirects=True
               )
               response.raise_for_status()

               # Check content type
               content_type = response.headers.get('content-type', '')
               if 'text/html' not in content_type.lower():
                   raise ValueError(f"Not HTML content: {content_type}")

               # Check size
               content = response.content
               max_size = 10 * 1024 * 1024  # 10MB
               if len(content) > max_size:
                   raise ValueError(f"Content too large: {len(content)} bytes")

               # Convert HTML to Markdown with security options
               markdown = to_markdown(content, parser_options=self.html_options)

               # Save output
               output_path = self.output_dir / output_filename
               output_path.write_text(markdown, encoding='utf-8')

               return {
                   'success': True,
                   'url': url,
                   'output_path': str(output_path),
                   'size': len(markdown)
               }

           except Exception as e:
               return {
                   'success': False,
                   'url': url,
                   'error': str(e)
               }

       def scrape_multiple(self, urls: list[str]) -> list[dict]:
           """Scrape multiple URLs."""
           results = []
           for i, url in enumerate(urls):
               # Generate filename from URL
               from urllib.parse import urlparse
               parsed = urlparse(url)
               filename = f"{parsed.netloc}_{i}.md".replace(':', '_')

               print(f"Scraping: {url}")
               result = self.scrape_url(url, filename)
               results.append(result)

               # Rate limiting
               import time
               time.sleep(1)

           return results

   # Usage
   scraper = SecureWebScraper(output_dir='./scraped_pages')

   urls = [
       'https://docs.python.org/3/library/pathlib.html',
       'https://requests.readthedocs.io/en/latest/',
       'https://github.com/psf/requests/blob/main/README.md'
   ]

   results = scraper.scrape_multiple(urls)

   # Print summary
   successful = [r for r in results if r['success']]
   failed = [r for r in results if not r['success']]

   print(f"\nSuccessful: {len(successful)}")
   print(f"Failed: {len(failed)}")

   if failed:
       print("\nFailed URLs:")
       for result in failed:
           print(f"  {result['url']}: {result['error']}")

**Key Security Features:**

- Strict host allowlisting for images
- HTTPS enforcement
- File:// URL blocking
- Content type validation
- Size limits
- Dangerous element stripping

LLM Data Preparation
--------------------

Text-Only Dataset Creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Process a large collection of mixed documents (PDF, DOCX) to create clean, text-only training data for LLM fine-tuning.

**Solution:**

.. code-block:: python

   import json
   from pathlib import Path
   from typing import List, Dict
   from all2md import to_markdown, PdfOptions, DocxOptions, MarkdownRendererOptions

   class LLMDatasetBuilder:
       """Build clean LLM training datasets from documents."""

       def __init__(self, output_dir: str):
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(parents=True, exist_ok=True)

           # Configure for clean, minimal markdown
           self.md_options = MarkdownRendererOptions(
               escape_special=False,  # Keep text readable
               use_hash_headings=True,
           )

           self.pdf_options = PdfOptions(
               attachment_mode="skip",  # No images
               extract_metadata=False,  # Skip metadata
               detect_columns=True,
               merge_hyphenated_words=True,
               enable_table_fallback_detection=True,
           )

           self.docx_options = DocxOptions(
               attachment_mode="skip",
               preserve_tables=True,
               extract_metadata=False,
           )

       def clean_text(self, text: str) -> str:
           """Clean and normalize text for LLM training."""
           # Remove excessive whitespace
           lines = []
           for line in text.split('\\n'):
               line = line.strip()
               if line:
                   lines.append(line)

           # Rejoin with consistent spacing
           text = '\\n'.join(lines)

           # Normalize multiple newlines
           while '\\n\\n\\n' in text:
               text = text.replace('\\n\\n\\n', '\\n\\n')

           return text

       def process_document(self, file_path: Path) -> Dict:
           """Process a single document."""
           try:
               # Select options based on format
               if file_path.suffix.lower() == '.pdf':
                   options = self.pdf_options
               elif file_path.suffix.lower() == '.docx':
                   options = self.docx_options
               else:
                   return {'success': False, 'error': 'Unsupported format'}

               # Convert to markdown
               content = to_markdown(
                   file_path,
                   parser_options=options,
                   renderer_options=self.md_options,
               )

               # Clean content
               content = self.clean_text(content)

               # Skip if too short
               word_count = len(content.split())
               if word_count < 100:
                   return {
                       'success': False,
                       'error': f'Document too short: {word_count} words'
                   }

               return {
                   'success': True,
                   'file_path': str(file_path),
                   'content': content,
                   'word_count': word_count,
                   'char_count': len(content)
               }

           except Exception as e:
               return {
                   'success': False,
                   'file_path': str(file_path),
                   'error': str(e)
               }

       def build_dataset(
           self,
           source_dirs: List[str],
           min_words: int = 100,
           max_words: int = 100000
       ) -> None:
           """Build complete training dataset."""
           all_documents = []
           stats = {
               'total_processed': 0,
               'successful': 0,
               'failed': 0,
               'total_words': 0,
               'total_chars': 0
           }

           # Collect all supported files
           supported_exts = {'.pdf', '.docx'}
           files = []
           for source_dir in source_dirs:
               path = Path(source_dir)
               files.extend([
                   f for f in path.rglob('*')
                   if f.suffix.lower() in supported_exts and f.is_file()
               ])

           print(f"Found {len(files)} documents to process")

           # Process each file
           for file_path in files:
               stats['total_processed'] += 1
               print(f"Processing [{stats['total_processed']}/{len(files)}]: {file_path.name}")

               result = self.process_document(file_path)

               if result['success']:
                   # Filter by word count
                   if min_words <= result['word_count'] <= max_words:
                       all_documents.append({
                           'text': result['content'],
                           'metadata': {
                               'source': str(file_path),
                               'word_count': result['word_count'],
                               'char_count': result['char_count']
                           }
                       })
                       stats['successful'] += 1
                       stats['total_words'] += result['word_count']
                       stats['total_chars'] += result['char_count']
                   else:
                       stats['failed'] += 1
                       print(f"  Skipped: word count {result['word_count']}")
               else:
                   stats['failed'] += 1
                   print(f"  Failed: {result.get('error', 'Unknown error')}")

           # Save dataset in JSONL format
           dataset_file = self.output_dir / "training_dataset.jsonl"
           with dataset_file.open('w', encoding='utf-8') as f:
               for doc in all_documents:
                   json.dump(doc, f, ensure_ascii=False)
                   f.write('\\n')

           # Save statistics
           stats_file = self.output_dir / "dataset_stats.json"
           stats_file.write_text(json.dumps(stats, indent=2))

           # Create plain text version (optional)
           plaintext_file = self.output_dir / "training_dataset.txt"
           with plaintext_file.open('w', encoding='utf-8') as f:
               for doc in all_documents:
                   f.write(doc['text'])
                   f.write('\\n\\n' + '='*80 + '\\n\\n')

           print(f"\\nDataset created:")
           print(f"  Documents: {stats['successful']}")
           print(f"  Total words: {stats['total_words']:,}")
           print(f"  Total chars: {stats['total_chars']:,}")
           print(f"  Output: {dataset_file}")

   # Usage
   builder = LLMDatasetBuilder(output_dir='./llm_dataset')
   builder.build_dataset(
       source_dirs=['./technical_docs', './user_manuals', './reports'],
       min_words=200,
       max_words=50000
   )

Dependency Management
---------------------

Production Readiness Checker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Verify that a production environment has all necessary converters installed before starting a document processing job.

**Solution:**

.. code-block:: python

   from pathlib import Path
   from typing import Dict, List, Set
   import sys

   # Import dependency checking utilities
   from all2md.dependencies import (
       check_package_installed,
       get_missing_packages_for_format,
       check_format_available
   )

   class DependencyValidator:
       """Validate converter dependencies for production."""

       def __init__(self):
           self.format_requirements = {
               'pdf': ['PyMuPDF'],
               'docx': ['python-docx'],
               'pptx': ['python-pptx'],
               'html': ['beautifulsoup4', 'lxml'],
               'xlsx': ['openpyxl'],
               'epub': ['ebooklib'],
               'odf': ['odfpy'],
               'rtf': ['pyth3']
           }

       def check_format(self, format_name: str) -> Dict:
           """Check if a specific format is available."""
           available = check_format_available(format_name)
           missing = get_missing_packages_for_format(format_name) if not available else []

           return {
               'format': format_name,
               'available': available,
               'missing_packages': missing
           }

       def check_all_formats(self) -> Dict:
           """Check all converter formats."""
           results = {}
           for format_name in self.format_requirements.keys():
               results[format_name] = self.check_format(format_name)

           return results

       def get_required_formats_for_files(self, files: List[Path]) -> Set[str]:
           """Determine which formats are needed for a set of files."""
           ext_to_format = {
               '.pdf': 'pdf',
               '.docx': 'docx',
               '.pptx': 'pptx',
               '.html': 'html',
               '.htm': 'html',
               '.xlsx': 'xlsx',
               '.csv': 'spreadsheet',
               '.epub': 'epub',
               '.odt': 'odf',
               '.odp': 'odf',
               '.rtf': 'rtf'
           }

           required = set()
           for file in files:
               fmt = ext_to_format.get(file.suffix.lower())
               if fmt:
                   required.add(fmt)

           return required

       def validate_for_job(self, input_dir: str) -> bool:
           """Validate dependencies for a processing job."""
           # Find all files
           input_path = Path(input_dir)
           files = list(input_path.rglob('*'))
           files = [f for f in files if f.is_file()]

           print(f"Validating dependencies for {len(files)} files in {input_dir}")

           # Determine required formats
           required_formats = self.get_required_formats_for_files(files)
           print(f"Required formats: {', '.join(required_formats)}")

           # Check each required format
           all_available = True
           missing_installs = []

           for fmt in required_formats:
               result = self.check_format(fmt)
               status = "✓" if result['available'] else "✗"
               print(f"  {status} {fmt}: ", end='')

               if result['available']:
                   print("OK")
               else:
                   print(f"MISSING - need {', '.join(result['missing_packages'])}")
                   all_available = False
                   missing_installs.extend(result['missing_packages'])

           if not all_available:
               print(f"\\nMissing packages: {', '.join(set(missing_installs))}")
               print(f"Install with: pip install {' '.join(set(missing_installs))}")
               return False

           print("\\nAll required converters are available!")
           return True

       def generate_requirements(self, formats: List[str]) -> str:
           """Generate requirements.txt content for formats."""
           all_packages = set()
           for fmt in formats:
               if fmt in self.format_requirements:
                   all_packages.update(self.format_requirements[fmt])

           return '\\n'.join(sorted(all_packages))

   # Usage Example 1: Check before processing
   def safe_batch_process(input_dir: str):
       """Only process if dependencies are met."""
       validator = DependencyValidator()

       if not validator.validate_for_job(input_dir):
           print("ERROR: Missing required dependencies")
           sys.exit(1)

       # Proceed with processing
       from all2md import to_markdown
       for file in Path(input_dir).rglob('*'):
           if file.is_file():
               try:
                   markdown = to_markdown(file)
                   print(f"Converted: {file}")
               except Exception as e:
                   print(f"Failed {file}: {e}")

   # Usage Example 2: Generate requirements
   validator = DependencyValidator()

   # For a specific job
   required_formats = ['pdf', 'docx', 'html']
   requirements = validator.generate_requirements(required_formats)
   Path('requirements.txt').write_text(requirements)
   print(f"Generated requirements.txt for: {', '.join(required_formats)}")

   # Usage Example 3: Pre-deployment check
   def pre_deploy_check():
       """Run before deploying to production."""
       validator = DependencyValidator()
       results = validator.check_all_formats()

       print("Dependency Check Report")
       print("=" * 40)

       available = []
       unavailable = []

       for fmt, info in results.items():
           if info['available']:
               available.append(fmt)
           else:
               unavailable.append(fmt)

       print(f"Available ({len(available)}): {', '.join(available)}")
       print(f"Unavailable ({len(unavailable)}): {', '.join(unavailable)}")

       return len(unavailable) == 0

   # Run check
   if __name__ == "__main__":
       pre_deploy_check()

AST-Based Analysis and Transformation
--------------------------------------

Document Structure Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Analyze document structure, extract metadata, and generate statistics using the AST.

**Solution:**

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeVisitor, Heading, Table, Link, Image, CodeBlock
   from pathlib import Path
   import json

   class DocumentAnalyzer(NodeVisitor):
       """Comprehensive document structure analyzer."""

       def __init__(self):
           self.stats = {
               'headings': [],
               'tables': 0,
               'code_blocks': 0,
               'links': [],
               'images': [],
               'word_count': 0,
               'structure': []
           }
           self.current_section = None

       def visit_heading(self, node: Heading):
           text = self._extract_text(node.content)
           heading_info = {
               'level': node.level,
               'text': text,
               'word_count': len(text.split())
           }
           self.stats['headings'].append(heading_info)

           # Track document structure
           self.current_section = text
           self.stats['structure'].append({
               'type': 'heading',
               'level': node.level,
               'text': text
           })

           self.generic_visit(node)

       def visit_table(self, node: Table):
           self.stats['tables'] += 1
           self.stats['structure'].append({
               'type': 'table',
               'section': self.current_section
           })
           self.generic_visit(node)

       def visit_code_block(self, node: CodeBlock):
           self.stats['code_blocks'] += 1
           self.stats['structure'].append({
               'type': 'code',
               'language': node.language,
               'section': self.current_section
           })
           self.generic_visit(node)

       def visit_link(self, node: Link):
           self.stats['links'].append({
               'url': node.url,
               'title': node.title,
               'section': self.current_section
           })
           self.generic_visit(node)

       def visit_image(self, node: Image):
           self.stats['images'].append({
               'url': node.url,
               'alt': node.alt_text,
               'section': self.current_section
           })
           self.generic_visit(node)

       def visit_text(self, node):
           from all2md.ast import Text
           if isinstance(node, Text):
               self.stats['word_count'] += len(node.content.split())

       def _extract_text(self, nodes):
           from all2md.ast import Text
           text = []
           for node in nodes:
               if isinstance(node, Text):
                   text.append(node.content)
               elif hasattr(node, 'content') and isinstance(node.content, list):
                   text.append(self._extract_text(node.content))
           return ''.join(text)

   def analyze_document(file_path: str) -> dict:
       """Analyze a document and return detailed statistics."""
       doc = to_ast(file_path)
       analyzer = DocumentAnalyzer()
       analyzer.visit(doc)

       # Generate summary
       stats = analyzer.stats
       stats['summary'] = {
           'total_headings': len(stats['headings']),
           'heading_breakdown': {},
           'total_tables': stats['tables'],
           'total_code_blocks': stats['code_blocks'],
           'total_links': len(stats['links']),
           'total_images': len(stats['images']),
           'total_words': stats['word_count']
       }

       # Count headings by level
       for h in stats['headings']:
           level = f"H{h['level']}"
           stats['summary']['heading_breakdown'][level] = \\
               stats['summary']['heading_breakdown'].get(level, 0) + 1

       return stats

   # Usage
   stats = analyze_document("report.pdf")

   print("Document Analysis Report")
   print("=" * 50)
   print(f"Total Words: {stats['summary']['total_words']:,}")
   print(f"Headings: {stats['summary']['total_headings']}")
   for level, count in stats['summary']['heading_breakdown'].items():
       print(f"  {level}: {count}")
   print(f"Tables: {stats['summary']['total_tables']}")
   print(f"Code Blocks: {stats['summary']['total_code_blocks']}")
   print(f"Links: {stats['summary']['total_links']}")
   print(f"Images: {stats['summary']['total_images']}")

   # Save detailed report
   Path("analysis_report.json").write_text(
       json.dumps(stats, indent=2)
   )

Batch Document Transformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** Apply consistent transformations across a collection of documents using AST.

**Solution:**

.. code-block:: python

   from pathlib import Path
   from all2md import to_ast
   from all2md.ast import (
       HeadingLevelTransformer,
       LinkRewriter,
       MarkdownRenderer,
       GFMFlavor
   )

   class DocumentTransformationPipeline:
       """Apply consistent transformations to document collections."""

       def __init__(self, output_dir: str):
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(parents=True, exist_ok=True)
           self.renderer = MarkdownRenderer(flavor=GFMFlavor())

       def transform_document(
           self,
           file_path: Path,
           transformers: list
       ) -> str:
           """Apply transformations to a single document."""
           # Convert to AST
           doc = to_ast(file_path)

           # Apply each transformer
           for transformer in transformers:
               doc = transformer.transform(doc)

           # Render back to Markdown
           return self.renderer.render(doc)

       def batch_transform(
           self,
           source_dir: str,
           transformers: list,
           pattern: str = "*.md"
       ) -> dict:
           """Transform all matching files in directory."""
           source_path = Path(source_dir)
           files = list(source_path.rglob(pattern))

           results = {
               'processed': 0,
               'successful': 0,
               'failed': 0,
               'files': []
           }

           for file_path in files:
               results['processed'] += 1
               print(f"Transforming: {file_path}")

               try:
                   # Transform document
                   transformed = self.transform_document(file_path, transformers)

                   # Save to output directory
                   relative_path = file_path.relative_to(source_path)
                   output_path = self.output_dir / relative_path
                   output_path.parent.mkdir(parents=True, exist_ok=True)
                   output_path.write_text(transformed, encoding='utf-8')

                   results['successful'] += 1
                   results['files'].append({
                       'source': str(file_path),
                       'output': str(output_path),
                       'success': True
                   })

               except Exception as e:
                   results['failed'] += 1
                   results['files'].append({
                       'source': str(file_path),
                       'error': str(e),
                       'success': False
                   })
                   print(f"  Error: {e}")

           return results

   # Usage Example 1: Increase all heading levels
   pipeline = DocumentTransformationPipeline(output_dir='./transformed_docs')

   transformers = [
       HeadingLevelTransformer(offset=1)  # H1 → H2, H2 → H3, etc.
   ]

   results = pipeline.batch_transform(
       source_dir='./original_docs',
       transformers=transformers,
       pattern='*.md'
   )

   print(f"Transformed {results['successful']}/{results['processed']} files")

   # Usage Example 2: Multiple transformations
   transformers = [
       HeadingLevelTransformer(offset=1),
       LinkRewriter(
           pattern=r'^/old-docs/',
           replacement='/new-docs/'
       )
   ]

   results = pipeline.batch_transform(
       source_dir='./docs',
       transformers=transformers
   )

Developer Workflows
-------------------

Live Documentation with Watch Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** You're writing documentation in various formats and want to automatically regenerate Markdown output as you edit source files.

**Solution:**

.. code-block:: bash

   # Watch a documentation directory
   all2md ./source-docs \
       --watch \
       --recursive \
       --output-dir ./docs-markdown \
       --watch-debounce 0.5 \
       --exclude "*.tmp" \
       --exclude "*.draft.*" \
       --log-file watch.log

   # Watch a single file during editing
   all2md my-guide.docx \
       --watch \
       --output-dir ./preview \
       --watch-debounce 0.3

   # Watch with specific format conversion
   all2md ./slides \
       --watch \
       --recursive \
       --format pptx \
       --output-dir ./markdown-slides \
       --pptx-include-slide-numbers

**Common Use Cases:**

* **Documentation Development:** Live preview of converted markdown
* **Content Authoring:** Real-time feedback when editing source documents
* **Testing:** Auto-convert test fixtures during development
* **CI/CD Integration:** Watch mode can be used in development containers

**Tips:**

* Use shorter debounce values (0.3-0.5s) for fast iteration
* Combine with ``--exclude`` to ignore temporary/backup files
* Use ``--log-file`` to track conversion issues without cluttering console
* Press ``Ctrl+C`` to stop watch mode

Creating Shareable Documentation Bundles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** You need to convert multiple documents and create a portable, organized ZIP archive with all assets properly structured.

**Solution:**

.. code-block:: bash

   # Create organized bundle with flat asset layout
   all2md ./project-docs \
       --recursive \
       --output-dir ./bundle \
       --assets-layout flat \
       --zip project-docs.zip \
       --attachment-mode download \
       --preserve-structure

   # Create per-document asset organization
   all2md report1.pdf report2.pdf report3.pdf \
       --output-dir ./reports \
       --assets-layout by-stem \
       --zip reports-bundle.zip \
       --attachment-mode download

   # Structured layout preserving directory hierarchy
   all2md ./company-docs \
       --recursive \
       --output-dir ./archive \
       --assets-layout structured \
       --zip company-archive.zip \
       --preserve-structure

**Asset Layout Comparison:**

* **flat**: All assets in single ``assets/`` directory - simplest, potential name conflicts
* **by-stem**: Assets organized by document name ``assets/{doc_name}/`` - clean separation
* **structured**: Preserves original directory structure - best for complex hierarchies

**Complete Example:**

.. code-block:: bash

   # Professional documentation bundle
   all2md ./technical-docs \
       --recursive \
       --output-dir ./output \
       --zip technical-docs-$(date +%Y%m%d).zip \
       --assets-layout by-stem \
       --attachment-mode download \
       --preserve-structure \
       --exclude "*.draft.*" \
       --exclude "*.tmp" \
       --parallel 4 \
       --skip-errors \
       --log-file conversion.log \
       --rich

This creates:
* Organized markdown files in ``output/``
* Assets organized per document in ``assets/{document_name}/``
* ZIP archive with timestamp
* Conversion log for troubleshooting

Debugging and Performance Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** You need to troubleshoot conversion issues or analyze performance bottlenecks in batch processing.

**Solution:**

.. code-block:: bash

   # Detailed trace logging for single file
   all2md complex-document.pdf \
       --trace \
       --log-file trace-output.log \
       --out result.md

   # Trace batch processing with timing
   all2md ./documents \
       --recursive \
       --output-dir ./converted \
       --trace \
       --log-file batch-trace.log \
       --skip-errors

   # Performance analysis of large conversion
   all2md huge-report.pdf \
       --trace \
       --log-file performance.log \
       --log-level DEBUG

**Analyzing Trace Output:**

The trace log includes detailed timing for each stage:

.. code-block:: text

   [2025-01-04 10:15:23] [DEBUG] [all2md] Starting: Parse PDF document
   [2025-01-04 10:15:25] [DEBUG] [all2md] Parsing (pdf) completed in 2.34s
   [2025-01-04 10:15:25] [DEBUG] [all2md] Starting: Apply transforms
   [2025-01-04 10:15:25] [DEBUG] [all2md] Transform pipeline completed in 0.12s
   [2025-01-04 10:15:25] [DEBUG] [all2md] Starting: Render to markdown
   [2025-01-04 10:15:26] [DEBUG] [all2md] Rendering completed in 0.89s

**System Information for Bug Reports:**

.. code-block:: bash

   # Get complete system info
   all2md --about > system-info.txt

   # Check specific format dependencies
   all2md check-deps pdf
   all2md check-deps docx

**Use Cases:**

* Identifying slow conversion stages
* Debugging complex document issues
* Collecting info for bug reports
* Performance optimization


Creating Custom Output Formats with Jinja2 Templates
-----------------------------------------------------

**Problem:** You need to convert documents to a custom format that isn't natively supported (e.g., DocBook XML, proprietary markup, YAML metadata) without writing Python code.

**Solution:** Use the Jinja2 template renderer to create custom output formats using templates.

Step 1: Create a Template File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a Jinja2 template for your desired output format. Save it as ``templates/docbook.xml.jinja2``:

.. code-block:: jinja

   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE article PUBLIC "-//OASIS//DTD DocBook XML V4.5//EN"
   "http://www.oasis-open.org/docbook/xml/4.5/docbookx.dtd">
   <article>
     <title>{{ metadata.title|escape_xml }}</title>

     {% if metadata.author %}
     <articleinfo>
       <author>
         <firstname>{{ metadata.author|escape_xml }}</firstname>
       </author>
     </articleinfo>
     {% endif %}

     {% for node in document.children %}
       {% if node|node_type == "Heading" %}
         {% if node.level == 1 %}
     <sect1>
       <title>{{ node.content|map('render')|join('')|escape_xml }}</title>
         {% elif node.level == 2 %}
     <sect2>
       <title>{{ node.content|map('render')|join('')|escape_xml }}</title>
         {% endif %}
       {% elif node|node_type == "Paragraph" %}
       <para>{{ node.content|map('render')|join('')|escape_xml }}</para>
       {% elif node|node_type == "CodeBlock" %}
       <programlisting{% if node.language %} language="{{ node.language }}"{% endif %}>
         {{- node.content|escape_xml -}}
       </programlisting>
       {% elif node|node_type == "List" %}
       <itemizedlist>
         {% for item in node.items %}
         <listitem>
           <para>{{ item|render|escape_xml }}</para>
         </listitem>
         {% endfor %}
       </itemizedlist>
       {% endif %}
     {% endfor %}
   </article>

Step 2: Convert Using Python API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the template to convert documents:

.. code-block:: python

   from all2md import from_markdown
   from all2md.options.jinja import JinjaRendererOptions

   # Configure the Jinja renderer
   options = JinjaRendererOptions(
       template_file='templates/docbook.xml.jinja2',
       escape_strategy='xml',                # Use XML escaping by default
       enable_escape_filters=True,           # Enable |escape_xml filter
       enable_traversal_helpers=True         # Enable get_headings() etc.
   )

   # Convert Markdown to DocBook XML
   from_markdown(
       'technical-doc.md',
       target_format='jinja',
       output='technical-doc.xml',
       renderer_options=options
   )

Step 3: Batch Process Multiple Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process entire directories:

.. code-block:: python

   from pathlib import Path
   from all2md import from_markdown
   from all2md.options.jinja import JinjaRendererOptions

   def convert_to_docbook(source_dir: str, output_dir: str):
       """Convert all Markdown files to DocBook XML."""
       source_path = Path(source_dir)
       output_path = Path(output_dir)
       output_path.mkdir(parents=True, exist_ok=True)

       options = JinjaRendererOptions(
           template_file='templates/docbook.xml.jinja2',
           escape_strategy='xml',
           enable_escape_filters=True,
           enable_traversal_helpers=True
       )

       for md_file in source_path.rglob('*.md'):
           # Create output path preserving directory structure
           relative_path = md_file.relative_to(source_path)
           output_file = output_path / relative_path.with_suffix('.xml')
           output_file.parent.mkdir(parents=True, exist_ok=True)

           print(f"Converting {md_file} -> {output_file}")

           try:
               from_markdown(
                   str(md_file),
                   target_format='jinja',
                   output=str(output_file),
                   renderer_options=options
               )
           except Exception as e:
               print(f"  Error: {e}")
               continue

   # Process all docs
   convert_to_docbook('docs/markdown', 'docs/docbook')

Advanced: Template with Custom Context
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add custom variables to templates:

.. code-block:: python

   from datetime import datetime
   from all2md import from_markdown
   from all2md.options.jinja import JinjaRendererOptions

   # Template with extra context
   template = """
   {%- set version = context_version -%}
   {%- set timestamp = context_timestamp -%}

   Document: {{ title }}
   Generated by {{ generator }} v{{ version }}
   Generated on {{ timestamp }}

   ---
   {% for h in headings %}
   {{ "  " * (h.level - 1) }}{{ loop.index }}. {{ h.text }}
   {%- endfor %}
   """

   options = JinjaRendererOptions(
       template_string=template,
       enable_traversal_helpers=True,
       extra_context={
           'context_version': '2.0.1',
           'context_timestamp': datetime.now().isoformat(),
           'generator': 'all2md'
       }
   )

   from_markdown('document.md', target_format='jinja', output='outline.txt', renderer_options=options)

Advanced: Multiple Output Formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generate multiple formats from one document:

.. code-block:: python

   from all2md import to_ast
   from all2md.renderers.jinja import JinjaRenderer
   from all2md.options.jinja import JinjaRendererOptions

   # Parse once
   doc = to_ast('report.md')

   # Generate DocBook XML
   xml_options = JinjaRendererOptions(
       template_file='templates/docbook.xml.jinja2',
       escape_strategy='xml'
   )
   xml_renderer = JinjaRenderer(xml_options)
   with open('report.xml', 'w', encoding='utf-8') as f:
       f.write(xml_renderer.render_to_string(doc))

   # Generate YAML metadata
   yaml_options = JinjaRendererOptions(
       template_file='templates/metadata.yaml.jinja2',
       escape_strategy='yaml',
       enable_traversal_helpers=True
   )
   yaml_renderer = JinjaRenderer(yaml_options)
   with open('report.yaml', 'w', encoding='utf-8') as f:
       f.write(yaml_renderer.render_to_string(doc))

   # Generate ANSI terminal output
   ansi_options = JinjaRendererOptions(
       template_file='templates/ansi-terminal.txt.jinja2',
       enable_traversal_helpers=True
   )
   ansi_renderer = JinjaRenderer(ansi_options)
   with open('report-terminal.txt', 'w', encoding='utf-8') as f:
       f.write(ansi_renderer.render_to_string(doc))

Template Gallery
~~~~~~~~~~~~~~~~

See the ``examples/jinja-templates/`` directory for production-ready templates:

* **docbook.xml.jinja2** - DocBook XML for technical documentation
* **metadata.yaml.jinja2** - YAML metadata and structure extraction
* **custom-outline.txt.jinja2** - Human-readable document outline
* **ansi-terminal.txt.jinja2** - Colorful terminal output with Unicode box drawing

**Key Features:**

* **No Python Required:** Create custom formats with just templates
* **Full AST Access:** Templates see the entire document structure
* **Rich Helpers:** 8 escape filters + 5 traversal functions built-in
* **Flexible:** Any text-based format (XML, YAML, custom markup, etc.)

**See Also:**

* :doc:`templates` - Complete template reference
* :doc:`bidirectional` - Custom formats section
* ``examples/jinja-templates/README.md`` - Template usage examples


Each recipe provides a complete, tested solution that you can adapt to your specific needs. The examples demonstrate both CLI and Python API approaches, with emphasis on real-world considerations like security, performance, and error handling.

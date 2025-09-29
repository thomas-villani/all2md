Recipes and Cookbook
====================

This cookbook provides practical solutions to common, complex problems when using all2md. Each recipe demonstrates real-world scenarios with complete, tested examples that you can adapt to your needs.

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
       "pptx.slide_numbers": true,
       "eml.convert_html_to_markdown": true
   }
   EOF

   # Convert all documents recursively with parallel processing
   all2md ./documents \
       --recursive \
       --parallel 4 \
       --output-dir ./markdown_output \
       --preserve-structure \
       --options-json conversion_config.json \
       --exclude "*.tmp" \
       --exclude "*.draft.*" \
       --skip-errors \
       --rich

**Python equivalent:**

.. code-block:: python

   import os
   from pathlib import Path
   from concurrent.futures import ThreadPoolExecutor
   from all2md import to_markdown, PdfOptions, HtmlOptions, PptxOptions, MarkdownOptions

   def convert_documents_parallel(source_dir: str, output_dir: str):
       # Create shared markdown options
       md_options = MarkdownOptions(
           emphasis_symbol="_",
           bullet_symbols="•◦▪",
           extract_metadata=True
       )

       # Define format-specific options
       options_map = {
           'pdf': PdfOptions(
               attachment_mode="download",
               attachment_output_dir="./extracted_media",
               detect_columns=True,
               markdown_options=md_options
           ),
           'html': HtmlOptions(
               attachment_mode="download",
               attachment_output_dir="./extracted_media",
               strip_dangerous_elements=True,
               markdown_options=md_options
           ),
           'pptx': PptxOptions(
               attachment_mode="download",
               attachment_output_dir="./extracted_media",
               slide_numbers=True,
               markdown_options=md_options
           )
       }

       def convert_file(file_path):
           try:
               # Get file extension to determine options
               ext = file_path.suffix.lower().lstrip('.')
               options = options_map.get(ext)

               # Convert to markdown
               markdown_content = to_markdown(file_path, options=options)

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
       --options-json web_archive_config.json \
       --collate \
       --out website_archive.md

**Python solution with metadata preservation:**

.. code-block:: python

   from pathlib import Path
   from datetime import datetime
   from all2md import to_markdown, HtmlOptions, MarkdownOptions

   def create_website_archive(html_dir: str, output_file: str):
       md_options = MarkdownOptions(
           escape_special=False,  # Keep text readable
           use_hash_headings=True,
           page_separator="=" * 80,
           page_separator_format="Page: {page_num} - {filename}",
           include_page_numbers=True
       )

       html_options = HtmlOptions(
           attachment_mode="skip",
           extract_title=True,
           strip_dangerous_elements=True,
           convert_nbsp=True,
           markdown_options=md_options
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
               markdown = to_markdown(html_file, options=html_options)

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
   from all2md import to_markdown, PdfOptions, DocxOptions, MarkdownOptions

   class LLMDataProcessor:
       def __init__(self, output_dir: str):
           self.output_dir = Path(output_dir)
           self.output_dir.mkdir(exist_ok=True)

           # Configure for clean, minimal markdown
           self.md_options = MarkdownOptions(
               escape_special=False,  # Don't escape for readability
               emphasis_symbol="*",
               bullet_symbols="*-+",
               use_hash_headings=True,
               page_separator="\\n---\\n",  # Clear page breaks
               include_page_numbers=False  # No page numbers for training
           )

           self.pdf_options = PdfOptions(
               attachment_mode="skip",  # No images in training data
               extract_metadata=True,
               detect_columns=True,
               merge_hyphenated_words=True,
               table_fallback_detection=True,
               markdown_options=self.md_options
           )

           self.docx_options = DocxOptions(
               attachment_mode="skip",
               preserve_tables=True,
               extract_metadata=True,
               markdown_options=self.md_options
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
               content = to_markdown(file_path, options=options)

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
   from all2md import to_markdown, HtmlOptions, PdfOptions, MarkdownOptions

   class SecureDocumentProcessor:
       """Secure document processor for web applications."""

       def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB default
           self.max_file_size = max_file_size

           # Security-focused markdown options
           self.md_options = MarkdownOptions(
               escape_special=True,  # Escape for security
               use_hash_headings=True
           )

           # Secure PDF processing
           self.pdf_options = PdfOptions(
               attachment_mode="skip",  # No file downloads in web context
               extract_metadata=False,  # Avoid potential metadata exploits
               markdown_options=self.md_options
           )

           # Secure HTML processing
           self.html_options = HtmlOptions(
               attachment_mode="skip",
               allow_remote_fetch=False,  # Prevent SSRF attacks
               allow_local_files=False,   # Prevent local file access
               strip_dangerous_elements=True,  # Remove scripts/styles
               require_https=True,
               network_timeout=5.0,
               max_image_size_bytes=1024 * 1024,  # 1MB image limit
               markdown_options=self.md_options
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
                       markdown_content = to_markdown(temp_file.name, options=options)

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
   from all2md import to_markdown, PdfOptions, DocxOptions, MarkdownOptions

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
           md_options = MarkdownOptions(
               emphasis_symbol="_",
               use_hash_headings=True
           )

           self.options_map = {
               '.pdf': PdfOptions(
                   attachment_mode="download",
                   attachment_output_dir=str(self.output_dir / "media"),
                   markdown_options=md_options
               ),
               '.docx': DocxOptions(
                   attachment_mode="download",
                   attachment_output_dir=str(self.output_dir / "media"),
                   markdown_options=md_options
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
               content = to_markdown(file_path, options=options)

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
   from all2md import to_markdown, EmlOptions, MarkdownOptions

   class EmailAnalyzer:
       """Advanced email processing and analysis."""

       def __init__(self):
           self.md_options = MarkdownOptions(
               use_hash_headings=True,
               escape_special=False,  # Keep email content readable
               page_separator="\\n" + "="*80 + "\\n"
           )

           self.eml_options = EmlOptions(
               include_headers=True,
               preserve_thread_structure=True,
               convert_html_to_markdown=True,
               clean_quotes=True,
               detect_reply_separators=True,
               clean_wrapped_urls=True,
               date_format_mode="iso8601",
               markdown_options=self.md_options
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
                   markdown_content = to_markdown(eml_file, options=self.eml_options)

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

Each recipe provides a complete, tested solution that you can adapt to your specific needs. The examples demonstrate both CLI and Python API approaches, with emphasis on real-world considerations like security, performance, and error handling.
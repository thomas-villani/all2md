Performance Tuning
==================

This guide covers performance optimization strategies, benchmarks, and best practices for efficient document conversion with all2md. Whether processing single large files or batches of documents, these techniques will help maximize throughput and minimize resource usage.

.. contents::
   :local:
   :depth: 2

Performance Characteristics
---------------------------

Format-Specific Performance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Different document formats have varying performance characteristics:

.. list-table:: Performance by Format
   :header-rows: 1
   :widths: 15 20 20 45

   * - Format
     - Speed
     - Memory Usage
     - Notes
   * - Plain Text
     - Fastest
     - Minimal
     - Direct streaming, no parsing overhead
   * - Markdown
     - Very Fast
     - Low
     - Simple regex-based parsing
   * - HTML
     - Fast
     - Low-Medium
     - BeautifulSoup parsing, depends on complexity
   * - DOCX
     - Fast
     - Medium
     - ZIP extraction + XML parsing
   * - PPTX
     - Fast-Medium
     - Medium
     - Similar to DOCX, slide-by-slide processing
   * - PDF
     - Medium-Slow
     - Medium-High
     - Complex layout analysis, depends on page count
   * - EPUB
     - Medium
     - Medium
     - Multiple HTML files, metadata extraction
   * - XLSX/CSV
     - Fast
     - Low-Medium
     - Spreadsheet row iteration
   * - Email (EML)
     - Fast
     - Low-Medium
     - MIME parsing, depends on attachments

Typical Throughput
~~~~~~~~~~~~~~~~~~

Expected processing speeds on modern hardware (4-core CPU, 16GB RAM):

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Document Type
     - Typical Throughput
     - Example
   * - Plain text files
     - 10-50 MB/sec
     - 50-page document: <1 second
   * - DOCX documents
     - 5-20 pages/sec
     - 100-page document: 5-20 seconds
   * - PPTX presentations
     - 10-50 slides/sec
     - 50-slide deck: 1-5 seconds
   * - PDF (text-based)
     - 2-10 pages/sec
     - 100-page PDF: 10-50 seconds
   * - PDF (image-heavy)
     - 0.5-2 pages/sec
     - 100-page PDF: 50-200 seconds
   * - HTML web pages
     - 50-200 pages/sec
     - Complex page: <1 second
   * - EPUB books
     - 5-20 chapters/sec
     - 300-page book: 5-30 seconds

.. note::

   Actual performance varies significantly based on document complexity, image count, table structures, and hardware capabilities.

Optimization Strategies
-----------------------

Selective Page Processing
~~~~~~~~~~~~~~~~~~~~~~~~~

For large documents, process only required pages:

.. code-block:: python

   from all2md import to_markdown, PdfOptions

   # Process only first 10 pages
   options = PdfOptions(pages=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
   markdown = to_markdown('large_document.pdf', parser_options=options)

   # Or use page ranges (CLI-style)
   markdown = to_markdown('large_document.pdf', pages="1-10")

   # Process specific chapters only
   markdown = to_markdown('large_document.pdf', pages="1,5,10-15")

Skip Expensive Features
~~~~~~~~~~~~~~~~~~~~~~~

Disable features you don't need:

.. code-block:: python

   from all2md.options import PdfOptions

   # Fastest PDF processing (minimal features)
   fast_options = PdfOptions(
       attachment_mode='skip',  # Don't process images
       detect_columns=False,     # Disable column detection
       enable_table_fallback_detection=False,  # Disable heuristic table detection
       extract_metadata=False    # Skip metadata extraction
   )

   markdown = to_markdown('document.pdf', parser_options=fast_options)

For HTML, disable sanitization if processing trusted content:

.. code-block:: python

   from all2md.options import HtmlOptions

   fast_html_options = HtmlOptions(
       strip_dangerous_elements=False,  # Skip sanitization
       attachment_mode='skip',           # Don't fetch images
       extract_metadata=False            # Skip metadata
   )

Optimize Attachment Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attachment processing can be expensive. Choose the right mode:

.. code-block:: python

   # Fastest: Skip all attachments
   options = PdfOptions(attachment_mode='skip')

   # Fast: Alt text only (no image processing)
   options = PdfOptions(attachment_mode='alt_text')

   # Slower: Base64 embedding (processes and encodes images)
   options = PdfOptions(attachment_mode='base64')

   # Slowest: Download to disk (file I/O overhead)
   options = PdfOptions(
       attachment_mode='download',
       attachment_output_dir='./images'
   )

Memory Management
-----------------

Large File Handling
~~~~~~~~~~~~~~~~~~~

For very large files, use chunked processing:

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import PdfOptions

   def process_large_pdf_in_chunks(pdf_path: str, chunk_size: int = 10) -> str:
       """Process large PDF in chunks to manage memory."""
       # First, determine total pages (quick metadata read)
       from all2md.utils.metadata import extract_metadata
       metadata = extract_metadata(pdf_path)
       total_pages = metadata.get('page_count', 0)

       all_markdown = []

       for start_page in range(1, total_pages + 1, chunk_size):
           end_page = min(start_page + chunk_size - 1, total_pages)
           page_list = list(range(start_page, end_page + 1))

           options = PdfOptions(
               pages=page_list,
               attachment_mode='skip'  # Further reduce memory
           )

           chunk_markdown = to_markdown(pdf_path, parser_options=options)
           all_markdown.append(chunk_markdown)

           # Optional: Force garbage collection
           import gc
           gc.collect()

       return '\n\n'.join(all_markdown)

   # Usage
   markdown = process_large_pdf_in_chunks('huge_document.pdf', chunk_size=20)

Memory Limits
~~~~~~~~~~~~~

Set resource limits for production environments:

.. code-block:: python

   import resource

   # Limit memory to 2GB (Linux/macOS)
   def set_memory_limit(max_mem_bytes: int):
       try:
           resource.setrlimit(
               resource.RLIMIT_AS,
               (max_mem_bytes, max_mem_bytes)
           )
       except Exception as e:
           print(f"Could not set memory limit: {e}")

   # Set 2GB limit
   set_memory_limit(2 * 1024 * 1024 * 1024)

For Docker deployments:

.. code-block:: bash

   # Limit container memory
   docker run -m 2g -v /docs:/docs your-image \
     all2md /docs/large.pdf

Batch Processing
----------------

Parallel Processing
~~~~~~~~~~~~~~~~~~~

Process multiple documents in parallel using multiprocessing:

.. code-block:: python

   from pathlib import Path
   from concurrent.futures import ProcessPoolExecutor, as_completed
   from all2md import to_markdown
   from all2md.options import PdfOptions

   def convert_single_file(pdf_path: Path) -> tuple[str, str]:
       """Convert a single PDF file."""
       try:
           options = PdfOptions(attachment_mode='skip')
           markdown = to_markdown(str(pdf_path), parser_options=options)
           return str(pdf_path), markdown
       except Exception as e:
           return str(pdf_path), f"ERROR: {e}"

   def batch_convert_parallel(
       pdf_directory: Path,
       max_workers: int = 4
   ) -> dict[str, str]:
       """Convert multiple PDFs in parallel."""
       pdf_files = list(pdf_directory.glob('*.pdf'))
       results = {}

       with ProcessPoolExecutor(max_workers=max_workers) as executor:
           # Submit all tasks
           future_to_path = {
               executor.submit(convert_single_file, pdf): pdf
               for pdf in pdf_files
           }

           # Collect results as they complete
           for future in as_completed(future_to_path):
               path, markdown = future.result()
               results[path] = markdown
               print(f"Completed: {Path(path).name}")

       return results

   # Usage
   results = batch_convert_parallel(
       Path('/path/to/pdfs'),
       max_workers=4  # Adjust based on CPU cores
   )

Optimal Worker Count
~~~~~~~~~~~~~~~~~~~~

Choose worker count based on workload:

.. code-block:: python

   import os
   from typing import Literal

   def optimal_worker_count(
       workload: Literal['cpu_bound', 'io_bound', 'mixed'] = 'mixed'
   ) -> int:
       """Determine optimal worker count based on workload type."""
       cpu_count = os.cpu_count() or 4

       if workload == 'cpu_bound':
           # CPU-intensive (PDF layout analysis, table detection)
           return cpu_count
       elif workload == 'io_bound':
           # I/O-intensive (many small files)
           return cpu_count * 2
       else:  # mixed
           # Balanced workload
           return cpu_count + 1

   # Usage
   workers = optimal_worker_count('cpu_bound')
   print(f"Using {workers} workers for CPU-intensive tasks")

Progress Tracking
~~~~~~~~~~~~~~~~~

Monitor batch processing progress:

.. code-block:: python

   from pathlib import Path
   from all2md import to_markdown
   from typing import Callable

   def batch_convert_with_progress(
       files: list[Path],
       progress_callback: Callable[[str, int, int], None] | None = None
   ) -> dict[str, str]:
       """Convert files with progress tracking."""
       results = {}
       total = len(files)

       for idx, file_path in enumerate(files, start=1):
           try:
               markdown = to_markdown(str(file_path))
               results[str(file_path)] = markdown

               if progress_callback:
                   progress_callback(str(file_path), idx, total)

           except Exception as e:
               results[str(file_path)] = f"ERROR: {e}"
               if progress_callback:
                   progress_callback(str(file_path), idx, total)

       return results

   # Usage with progress
   def print_progress(filename: str, current: int, total: int):
       percent = (current / total) * 100
       print(f"[{current}/{total}] ({percent:.1f}%) {Path(filename).name}")

   results = batch_convert_with_progress(
       list(Path('/docs').glob('*.pdf')),
       progress_callback=print_progress
   )

Caching Strategies
------------------

Result Caching
~~~~~~~~~~~~~~

Cache conversion results to avoid reprocessing:

.. code-block:: python

   import hashlib
   import json
   from pathlib import Path
   from all2md import to_markdown

   class ConversionCache:
       """Simple file-based cache for conversion results."""

       def __init__(self, cache_dir: Path):
           self.cache_dir = cache_dir
           self.cache_dir.mkdir(parents=True, exist_ok=True)

       def _get_cache_key(self, file_path: Path) -> str:
           """Generate cache key from file content hash."""
           with open(file_path, 'rb') as f:
               content = f.read()
               return hashlib.sha256(content).hexdigest()

       def get(self, file_path: Path) -> str | None:
           """Get cached result if available."""
           cache_key = self._get_cache_key(file_path)
           cache_file = self.cache_dir / f"{cache_key}.md"

           if cache_file.exists():
               return cache_file.read_text(encoding='utf-8')
           return None

       def set(self, file_path: Path, markdown: str) -> None:
           """Cache conversion result."""
           cache_key = self._get_cache_key(file_path)
           cache_file = self.cache_dir / f"{cache_key}.md"
           cache_file.write_text(markdown, encoding='utf-8')

       def convert_with_cache(self, file_path: Path) -> str:
           """Convert with automatic caching."""
           cached = self.get(file_path)
           if cached:
               print(f"Cache hit: {file_path.name}")
               return cached

           print(f"Converting: {file_path.name}")
           markdown = to_markdown(str(file_path))
           self.set(file_path, markdown)
           return markdown

   # Usage
   cache = ConversionCache(Path('.cache'))
   markdown = cache.convert_with_cache(Path('document.pdf'))

Metadata Caching
~~~~~~~~~~~~~~~~

Cache expensive metadata extraction:

.. code-block:: python

   import pickle
   from pathlib import Path
   from all2md.utils.metadata import extract_metadata

   def get_metadata_cached(file_path: Path, cache_dir: Path) -> dict:
       """Get file metadata with caching."""
       cache_file = cache_dir / f"{file_path.stem}.meta"

       # Check if cached metadata is fresh
       if cache_file.exists():
           file_mtime = file_path.stat().st_mtime
           cache_mtime = cache_file.stat().st_mtime

           if cache_mtime >= file_mtime:
               with open(cache_file, 'rb') as f:
                   return pickle.load(f)

       # Extract fresh metadata
       metadata = extract_metadata(str(file_path))

       # Cache it
       cache_dir.mkdir(parents=True, exist_ok=True)
       with open(cache_file, 'wb') as f:
           pickle.dump(metadata, f)

       return metadata

Profiling and Debugging
-----------------------

Timing Individual Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measure conversion time:

.. code-block:: python

   import time
   from all2md import to_markdown

   def time_conversion(file_path: str) -> tuple[str, float]:
       """Time document conversion."""
       start = time.perf_counter()
       markdown = to_markdown(file_path)
       elapsed = time.perf_counter() - start

       print(f"Conversion took {elapsed:.2f} seconds")
       return markdown, elapsed

   markdown, duration = time_conversion('document.pdf')

Detailed Profiling
~~~~~~~~~~~~~~~~~~

Profile with cProfile for bottleneck identification:

.. code-block:: python

   import cProfile
   import pstats
   from io import StringIO
   from all2md import to_markdown

   def profile_conversion(file_path: str):
       """Profile conversion to identify bottlenecks."""
       profiler = cProfile.Profile()
       profiler.enable()

       # Run conversion
       markdown = to_markdown(file_path)

       profiler.disable()

       # Print stats
       stream = StringIO()
       stats = pstats.Stats(profiler, stream=stream)
       stats.sort_stats('cumulative')
       stats.print_stats(20)  # Top 20 functions

       print(stream.getvalue())
       return markdown

   # Usage
   profile_conversion('complex_document.pdf')

Memory Profiling
~~~~~~~~~~~~~~~~

Track memory usage with memory_profiler:

.. code-block:: bash

   # Install memory_profiler
   pip install memory-profiler

.. code-block:: python

   from memory_profiler import profile
   from all2md import to_markdown

   @profile
   def convert_with_memory_tracking(file_path: str) -> str:
       """Convert document with line-by-line memory tracking."""
       markdown = to_markdown(file_path)
       return markdown

   # Run with: python -m memory_profiler script.py
   convert_with_memory_tracking('large_document.pdf')

Configuration for Performance
------------------------------

Fast Configuration Presets
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Maximum Speed (Minimal Features):**

.. code-block:: python

   from all2md.options import PdfOptions

   speed_options = PdfOptions(
       attachment_mode='skip',
       detect_columns=False,
       enable_table_fallback_detection=False,
       extract_metadata=False
   )

**Balanced (Good Speed, Key Features):**

.. code-block:: python

   balanced_options = PdfOptions(
       attachment_mode='alt_text',  # Alt text only
       detect_columns=True,          # Keep layout detection
       enable_table_fallback_detection=True,  # Keep tables
       extract_metadata=False        # Skip metadata
   )

**Quality (Full Features, Slower):**

.. code-block:: python

   quality_options = PdfOptions(
       attachment_mode='base64',     # Embed images
       detect_columns=True,
       enable_table_fallback_detection=True,
       extract_metadata=True,
       preserve_text_formatting=True  # Preserve bold/italic
   )

CLI Performance Flags
~~~~~~~~~~~~~~~~~~~~~

Command-line performance optimization:

.. code-block:: bash

   # Fastest: Skip everything optional
   all2md document.pdf \
     --attachment-mode skip \
     --pdf-no-detect-columns \
     --pdf-no-enable-table-fallback-detection

   # Process specific pages only
   all2md large.pdf --pdf-pages "1-10"

   # Batch process with xargs (Unix)
   find /docs -name "*.pdf" -print0 | \
     xargs -0 -P 4 -I {} all2md {} --out {}.md

Environment Tuning
~~~~~~~~~~~~~~~~~~

Set environment variables for global performance tuning:

.. code-block:: bash

   # Disable network globally for speed
   export ALL2MD_DISABLE_NETWORK=1

   # Set attachment mode globally
   export ALL2MD_ATTACHMENT_MODE=skip

Hardware Recommendations
------------------------

CPU
~~~

* **Minimum**: 2 cores, 2.0 GHz
* **Recommended**: 4+ cores, 3.0+ GHz
* **Optimal**: 8+ cores for batch processing

RAM
~~~

* **Minimum**: 4 GB (for small documents)
* **Recommended**: 8-16 GB (for typical workloads)
* **Large files**: 32+ GB (for very large PDFs or batch processing)

Storage
~~~~~~~

* **HDD**: Adequate for most workloads
* **SSD**: 2-3x faster for batch processing (reduced I/O latency)
* **NVMe**: Best for high-throughput batch processing

Real-World Examples
-------------------

Web Service Optimization
~~~~~~~~~~~~~~~~~~~~~~~~

Optimize for web service deployment:

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import PdfOptions, HtmlOptions
   import tempfile
   from pathlib import Path

   class OptimizedConverter:
       """Optimized converter for web services."""

       def __init__(self, max_pages: int = 50, max_file_size: int = 10*1024*1024):
           self.max_pages = max_pages
           self.max_file_size = max_file_size

       def convert_upload(self, file_data: bytes, filename: str) -> str:
           """Convert uploaded file with safety limits."""
           # Validate file size
           if len(file_data) > self.max_file_size:
               raise ValueError(f"File too large: {len(file_data)} bytes")

           # Write to temp file
           with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix) as tmp:
               tmp.write(file_data)
               tmp.flush()

               # Determine format and options
               if filename.endswith('.pdf'):
                   options = PdfOptions(
                       pages=list(range(1, self.max_pages + 1)),
                       attachment_mode='skip',  # Fast, no security issues
                       detect_columns=True,
                       enable_table_fallback_detection=False  # Speed up
                   )
               elif filename.endswith(('.html', '.htm')):
                   options = HtmlOptions(
                       strip_dangerous_elements=True,
                       attachment_mode='skip',
                       network=None  # Network disabled by env var
                   )
               else:
                   options = None

               # Convert with timeout protection (implement externally)
               markdown = to_markdown(tmp.name, parser_options=options)

               # Limit output size
               max_output = 1024 * 1024  # 1MB
               if len(markdown) > max_output:
                   markdown = markdown[:max_output] + "\n\n[Output truncated]"

               return markdown

Data Pipeline Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~

Optimize for ETL/data pipeline scenarios:

.. code-block:: python

   from pathlib import Path
   from concurrent.futures import ProcessPoolExecutor
   from all2md import to_markdown
   from all2md.options import DocxOptions
   import logging

   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)

   def process_document_pipeline(
       input_dir: Path,
       output_dir: Path,
       workers: int = 4
   ):
       """Process documents in pipeline with optimization."""
       output_dir.mkdir(parents=True, exist_ok=True)

       # Gather files
       files = list(input_dir.rglob('*.docx'))
       logger.info(f"Found {len(files)} files to process")

       # Prepare options (shared across workers)
       options = DocxOptions(
           attachment_mode='skip',  # Fastest
           preserve_tables=True,
           extract_metadata=False
       )

       def process_single(file_path: Path) -> tuple[Path, bool]:
           """Process single file."""
           try:
               output_path = output_dir / f"{file_path.stem}.md"

               # Skip if already processed
               if output_path.exists():
                   logger.info(f"Skipping (exists): {file_path.name}")
                   return file_path, True

               markdown = to_markdown(str(file_path), parser_options=options)
               output_path.write_text(markdown, encoding='utf-8')
               logger.info(f"Converted: {file_path.name}")
               return file_path, True

           except Exception as e:
               logger.error(f"Failed {file_path.name}: {e}")
               return file_path, False

       # Process in parallel
       with ProcessPoolExecutor(max_workers=workers) as executor:
           results = list(executor.map(process_single, files))

       # Summary
       successful = sum(1 for _, success in results if success)
       logger.info(f"Pipeline complete: {successful}/{len(files)} successful")

   # Usage
   process_document_pipeline(
       Path('/data/input/documents'),
       Path('/data/output/markdown'),
       workers=8
   )

Benchmarking Your Workload
---------------------------

Create custom benchmarks:

.. code-block:: python

   from pathlib import Path
   from all2md import to_markdown
   from all2md.options import PdfOptions
   import time
   import statistics

   def benchmark_conversion(
       file_path: Path,
       iterations: int = 5,
       options: PdfOptions | None = None
   ) -> dict:
       """Benchmark conversion performance."""
       times = []

       for i in range(iterations):
           start = time.perf_counter()
           markdown = to_markdown(str(file_path), parser_options=options)
           elapsed = time.perf_counter() - start
           times.append(elapsed)
           print(f"  Run {i+1}: {elapsed:.3f}s")

       return {
           'file': str(file_path),
           'iterations': iterations,
           'mean': statistics.mean(times),
           'median': statistics.median(times),
           'stdev': statistics.stdev(times) if len(times) > 1 else 0,
           'min': min(times),
           'max': max(times),
           'total_time': sum(times)
       }

   # Usage
   print("Benchmarking PDF conversion:")
   results = benchmark_conversion(
       Path('test_document.pdf'),
       iterations=5,
       options=PdfOptions(attachment_mode='skip')
   )

   print(f"\nResults:")
   print(f"  Mean: {results['mean']:.3f}s")
   print(f"  Median: {results['median']:.3f}s")
   print(f"  Std Dev: {results['stdev']:.3f}s")
   print(f"  Range: {results['min']:.3f}s - {results['max']:.3f}s")

See Also
--------

* :doc:`cli` - Command-line performance options
* :doc:`troubleshooting` - Performance issue troubleshooting
* :doc:`integrations` - Integration-specific optimizations

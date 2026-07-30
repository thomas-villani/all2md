# Performance Benchmarking for all2md

This directory contains performance benchmarking tests for the all2md document conversion library. These tests measure conversion speed, throughput, and resource usage across different document formats.

## What these gate on

**Conversion, not time.** Each benchmark asserts that its format still converts and produces a non-empty document. That is deterministic and cannot flake.

Timings are *recorded* — printed, and written to `results/` under `--benchmark-save` — and deliberately left ungated. They used to be gated, and it was theatre: the first time anyone actually ran this suite, the absolute ceilings had **11x–231x headroom** (`basic.xlsx` at 13 ms against a 3 s limit), so a conversion had to get two orders of magnitude slower before one fired. The remaining assertions compared `mean_time > 0` against the mean of `perf_counter` deltas, which is true by construction.

Nothing had ever run them to notice, because a bare `pytest tests/` deselects everything marked `benchmark`.

Gating these numbers for real needs a variance study on the runners first: these fixtures convert in 5–885 ms, measured CI runner variance is already ~7%, and denominator jitter on a small measurement is worse. `benchmarks/startup.py` shows what that costs to get right — it needs two metrics that agree before it will go red. The CI artifact is what such a study would be built from.

For regression detection over *real* documents rather than small fixtures, see `benchmarks/corpus/`, which gates the failure set against a committed baseline.

## Quick Start

### Running Benchmarks

Run all benchmark tests:
```bash
pytest tests/performance --benchmark
```

Run benchmarks for a specific format:
```bash
pytest tests/performance --benchmark -m pdf
pytest tests/performance --benchmark -m docx
pytest tests/performance --benchmark -m html
```

Save results to CSV and JSON:
```bash
pytest tests/performance --benchmark --benchmark-save
```

Custom number of iterations:
```bash
pytest tests/performance --benchmark --benchmark-iterations=10
```

## Available Benchmarks

### Format-Specific Benchmarks

- **PDF**: `test_benchmark_pdf_basic`, `test_benchmark_pdf_complex`
- **DOCX**: `test_benchmark_docx_basic`, `test_benchmark_docx_complex`, `test_benchmark_docx_footnotes`
- **HTML**: `test_benchmark_html_basic`, `test_benchmark_html_readability`
- **PPTX**: `test_benchmark_pptx_basic`
- **XLSX**: `test_benchmark_xlsx_basic`
- **ODT/ODP**: `test_benchmark_odt_basic`, `test_benchmark_odt_complex`
- **EPUB**: `test_benchmark_epub_simple`
- **IPYNB**: `test_benchmark_ipynb_simple`
- **MHTML**: `test_benchmark_mhtml_simple`
- **CSV**: `test_benchmark_csv_basic`
- **RTF**: `test_benchmark_rtf_basic`

### Special Benchmarks

- **Round-trip**: Tests conversion chains (e.g., MD → DOCX → MD)
- **Batch**: Tests converting multiple files sequentially

## Understanding Results

### Console Output

After running benchmarks, you'll see a summary table:

```
================================================================================
BENCHMARK RESULTS SUMMARY
================================================================================
Format       File                           Size       Mean         Throughput
--------------------------------------------------------------------------------
pdf          basic.pdf                      116.00 KB  245ms        0.46 MB/s
docx         basic.docx                     20.00 KB   89ms         0.22 MB/s
html         basic.html                     5.30 KB    12ms         0.43 MB/s
================================================================================
```

### Metrics Explained

- **Format**: Document format being tested
- **File**: Name of the test file
- **Size**: File size (KB or MB)
- **Mean**: Average conversion time across iterations
- **Throughput**: Processing speed in MB/second

### Saved Results

When using `--benchmark-save`, results are saved to:
- `tests/performance/results/benchmark_results_<timestamp>.csv`
- `tests/performance/results/benchmark_results_<timestamp>.json`

#### CSV Format

```csv
format,file_path,file_size,file_size_mb,iterations,mean_time,median_time,min_time,max_time,std_dev,throughput_mbps,git_commit,timestamp
pdf,tests/fixtures/documents/basic.pdf,118784,0.11,5,0.245,0.243,0.238,0.256,0.007,0.46,a1b2c3d4,2025-01-15T10:30:45
```

#### JSON Format

```json
{
  "benchmark_run": {
    "timestamp": "2025-01-15T10:30:45.123456",
    "warmup_iterations": 1,
    "default_iterations": 3
  },
  "results": [
    {
      "format": "pdf",
      "file_path": "tests/fixtures/documents/basic.pdf",
      "file_size": 118784,
      "file_size_mb": 0.11,
      "iterations": 5,
      "timings": [0.238, 0.243, 0.245, 0.251, 0.256],
      "mean_time": 0.2466,
      "median_time": 0.245,
      "min_time": 0.238,
      "max_time": 0.256,
      "std_dev": 0.0067,
      "throughput_mbps": 0.46,
      "mean_formatted": "247ms",
      "metadata": {
        "git_commit": "a1b2c3d4",
        "timestamp": "2025-01-15T10:30:45.123456"
      }
    }
  ]
}
```

## Test Files

Benchmarks use test files from `tests/fixtures/documents/`:

### Pre-existing Files
- `basic.pdf`, `complex.pdf` - PDF documents
- `basic.docx`, `complex.docx` - Word documents
- `basic.html` - HTML file
- `basic.xlsx` - Excel spreadsheet
- `basic.pptx` - PowerPoint presentation
- `basic.odt`, `complex.odt` - OpenDocument text

### Generated Fixtures
Files in `tests/fixtures/documents/generated/` are created by fixture generators:
- EPUB: `epub-simple.epub`, `epub-images.epub`
- Jupyter: `ipynb-simple.ipynb`, `ipynb-images.ipynb`
- MHTML: `mhtml-simple.mht`
- And more...

## Customization

### Creating Custom Benchmarks

```python
import pytest
from pathlib import Path

@pytest.mark.benchmark
def test_my_custom_benchmark(benchmark_runner):
    """My custom benchmark test."""
    test_file = Path("path/to/my/file.pdf")

    result = benchmark_runner.run(
        format_name='pdf',
        file_path=test_file,
        iterations=5,
        # Optional: pass converter options
        extract_images=True,
        table_strategy='full'
    )

    # Assert performance requirements
    assert result.mean_time < 1.0  # Should complete in < 1 second
    assert result.throughput_mbps > 0.5  # Should process > 0.5 MB/s
```

### Custom Conversion Functions

```python
from all2md import convert

@pytest.mark.benchmark
def test_custom_conversion_func(benchmark_runner):
    """Benchmark with custom conversion logic."""

    def my_conversion(file_path):
        # Custom conversion logic
        return convert(
            file_path,
            input_format='pdf',
            output_format='html'
        )

    result = benchmark_runner.run(
        format_name='pdf->html',
        file_path=Path('test.pdf'),
        conversion_func=my_conversion
    )
```

## Performance Tips

### Interpreting Results

1. **Warmup Iterations**: First iteration is often slower due to Python import caching and JIT compilation. Results exclude 1 warmup run by default.

2. **Variance**: High standard deviation may indicate:
   - System load interference
   - File I/O caching effects
   - Non-deterministic processing

3. **Throughput**: MB/s metric useful for:
   - Comparing similar file types
   - Detecting regressions
   - Capacity planning

### Best Practices

- Run benchmarks on an idle system
- Use consistent hardware for comparisons
- Run multiple iterations (5-10) for statistical significance
- Save results to track performance over time
- Compare against git commits to detect regressions

### CI/CD Integration

The `Format Benchmarks` job in `.github/workflows/ci.yml` runs this suite on every
push and pull request and uploads `results/` as a `format-benchmarks-<run>` artifact.
The job fails only if a format stops converting or converts to nothing — never on a
timing number.

`results/` is gitignored. Download the artifact to compare runs; a committed snapshot
only tells you about one machine on one day, which is why the two that used to live
here were removed.

## Analyzing Results

### Compare Across Commits

```bash
# Run benchmark and save
pytest tests/performance --benchmark --benchmark-save

# Later, after code changes
pytest tests/performance --benchmark --benchmark-save

# Compare results manually using CSV/JSON files
```

### Statistical Analysis

Results include:
- **Mean**: Average time across iterations
- **Median**: Middle value (robust to outliers)
- **Min/Max**: Best and worst case
- **Std Dev**: Consistency indicator
- **Throughput**: Processing speed

### Regression Detection

A single run tells you very little here. Treat a difference as real only if it
survives the noise floor, which on these fixtures is large: measured CI runner
variance is ~7% before you account for the denominator jitter that dominates a
5–15 ms measurement, and a different CPU class shifts *every* number by ~18% at once.

So a 20%-style rule of thumb is not a threshold, it is a prompt to look — and to
look at whether the whole table moved together, which means the machine changed
rather than the code. `benchmarks/startup.py` handles exactly that by requiring a raw
and an interpreter-relative delta to agree before it reports a regression.

## Troubleshooting

### Tests Not Running

Make sure to include `--benchmark` flag:
```bash
pytest tests/performance --benchmark
```

Without the flag, benchmark tests are automatically skipped.

### Missing Test Files

Some tests skip if fixture files don't exist:
```
SKIPPED [1] test file not found: tests/fixtures/documents/basic.pdf
```

Generate fixtures using:
```bash
python -m tests.fixtures.generators
```

### Slow Performance

If benchmarks are too slow:
- Reduce iterations: `--benchmark-iterations=1`
- Run specific format: `-m pdf`
- Skip slow tests: `-m "benchmark and not slow"`

## Advanced Usage

### Profiling Individual Conversions

```python
import cProfile
import pstats
from all2md import to_markdown

def profile_conversion():
    profiler = cProfile.Profile()
    profiler.enable()

    to_markdown('large_file.pdf')

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

profile_conversion()
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def test_memory_usage():
    from all2md import to_markdown
    to_markdown('large_file.pdf')
```

## Contributing

When adding new benchmarks:

1. Use `@pytest.mark.benchmark` decorator
2. Add appropriate format markers (`@pytest.mark.pdf`, etc.)
3. Include assertions for performance requirements
4. Document expected performance characteristics
5. Use existing test fixtures when possible

## Questions?

For questions or issues with performance testing:
- Check existing test implementations in `test_benchmark.py`
- Review `conftest.py` for available fixtures and utilities
- Consult main project documentation

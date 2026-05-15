# all2md corpus benchmark

_Generated from `results_20260506_192118.json` at 2026-05-06 23:21 UTC_

- **all2md**: 1.1.0 (`b0e422479436`)
- **Python**: 3.13.5
- **Platform**: Windows-11-10.0.26200-SP0
- **Documents**: 160 total, 159 ok, 1 failed
- **Wall time** (successful conversions): 21.4m over 107.38 MB = 0.08 MB/s

## Per-source

| source | n | ok | fail | total bytes | p50 | p95 | mean | MB/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| arxiv | 30 | 30 | 0 | 72.38 MB | 12.24s | 56.87s | 19.78s | 0.12 |
| enron | 50 | 50 | 0 | 113.6 KB | 13ms | 25ms | 15ms | 0.15 |
| govdocs1 | 50 | 50 | 0 | 30.99 MB | 5.91s | 1.0m | 13.72s | 0.05 |
| poi | 30 | 29 | 1 | 3.90 MB | 21ms | 281ms | 54ms | 2.48 |

## Per-format

| format | n | ok | fail | total bytes | p50 | p95 | mean | MB/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| docx | 17 | 17 | 0 | 396.3 KB | 16ms | 314ms | 64ms | 0.36 |
| eml | 50 | 50 | 0 | 113.6 KB | 13ms | 25ms | 15ms | 0.15 |
| pdf | 80 | 80 | 0 | 103.37 MB | 8.54s | 1.1m | 15.99s | 0.08 |
| pptx | 13 | 12 | 1 | 3.51 MB | 28ms | 89ms | 41ms | 7.14 |

## Top 10 slowest

| # | source | format | size | time | doc |
|---:|---|---|---:|---:|---|
| 1 | govdocs1 | pdf | 1.25 MB | 2.1m | `000/000887.pdf` |
| 2 | govdocs1 | pdf | 3.74 MB | 1.3m | `000/000282.pdf` |
| 3 | govdocs1 | pdf | 4.20 MB | 1.2m | `000/000152.pdf` |
| 4 | arxiv | pdf | 4.08 MB | 1.1m | `2605.03701v1` |
| 5 | arxiv | pdf | 15.53 MB | 1.1m | `2605.03596v1` |
| 6 | govdocs1 | pdf | 2.28 MB | 49.35s | `000/000762.pdf` |
| 7 | arxiv | pdf | 3.86 MB | 45.62s | `2605.03096v1` |
| 8 | arxiv | pdf | 1003.4 KB | 41.43s | `2605.02801v1` |
| 9 | arxiv | pdf | 3.62 MB | 41.29s | `2605.01188v1` |
| 10 | govdocs1 | pdf | 1.59 MB | 38.48s | `000/000359.pdf` |

## Failures (1)

**MalformedFileError** (1)

- `poi/test-data/slideshow/crash-57308ca363f5b71763c489d1b432aff009d4bc4f.pptx` (72.6 KB): all2md.exceptions.MalformedFileError: Failed to open PPTX presentation: BadZipFile("Bad CRC-32 for file 'ppt/slideMasters/slideMaster1.xml'")

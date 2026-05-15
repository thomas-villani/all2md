# all2md corpus benchmark

_Generated from `results_20260515_153546.json` at 2026-05-15 19:35 UTC_

- **all2md**: 1.1.0 (`3f6fce6d7ebc`)
- **Python**: 3.13.5
- **Platform**: Windows-11-10.0.26200-SP0
- **Documents**: 149 total, 149 ok, 0 failed
- **Wall time** (successful conversions): 6.7m over 148.35 MB = 0.37 MB/s

## Per-source

| source | n | ok | fail | total bytes | p50 | p95 | mean | MB/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| arxiv | 30 | 30 | 0 | 115.87 MB | 3.80s | 1.1m | 11.53s | 0.33 |
| enron | 50 | 50 | 0 | 113.6 KB | 10ms | 15ms | 11ms | 0.21 |
| govdocs1 | 50 | 50 | 0 | 30.99 MB | 194ms | 5.02s | 1.08s | 0.58 |
| poi | 19 | 19 | 0 | 1.38 MB | 18ms | 338ms | 86ms | 0.84 |

## Per-format

| format | n | ok | fail | total bytes | p50 | p95 | mean | MB/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| docx | 14 | 14 | 0 | 356.6 KB | 16ms | 281ms | 68ms | 0.36 |
| eml | 50 | 50 | 0 | 113.6 KB | 10ms | 15ms | 11ms | 0.21 |
| pdf | 80 | 80 | 0 | 146.86 MB | 728ms | 13.50s | 5.00s | 0.37 |
| pptx | 5 | 5 | 0 | 1.03 MB | 34ms | 356ms | 135ms | 1.52 |

## Top 10 slowest

| # | source | format | size | time | doc |
|---:|---|---|---:|---:|---|
| 1 | arxiv | pdf | 4.96 MB | 1.8m | `2605.13411v1` |
| 2 | arxiv | pdf | 2.39 MB | 1.4m | `2605.13841v1` |
| 3 | arxiv | pdf | 39.09 MB | 48.42s | `2605.15128v1` |
| 4 | arxiv | pdf | 6.71 MB | 13.52s | `2605.13277v1` |
| 5 | govdocs1 | pdf | 4.20 MB | 13.50s | `000/000152.pdf` |
| 6 | govdocs1 | pdf | 1.25 MB | 11.65s | `000/000887.pdf` |
| 7 | arxiv | pdf | 2.49 MB | 8.99s | `2605.15155v1` |
| 8 | arxiv | pdf | 4.51 MB | 6.91s | `2605.14531v1` |
| 9 | arxiv | pdf | 658.0 KB | 6.56s | `2605.12933v1` |
| 10 | arxiv | pdf | 784.3 KB | 6.28s | `2605.15011v1` |

## Failures (0)

_No failures._

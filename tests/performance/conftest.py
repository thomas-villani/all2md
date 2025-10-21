"""Pytest fixtures and utilities for performance benchmarking tests."""

import csv
import json
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

from all2md import to_markdown
from all2md.cli.timing import OperationTimer, format_duration


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run.

    Attributes
    ----------
    format_name : str
        Document format being tested
    file_path : Path
        Path to the test file
    file_size : int
        File size in bytes
    iterations : int
        Number of iterations run
    timings : list of float
        Individual timing results for each iteration
    mean_time : float
        Mean conversion time in seconds
    median_time : float
        Median conversion time in seconds
    min_time : float
        Minimum conversion time in seconds
    max_time : float
        Maximum conversion time in seconds
    std_dev : float
        Standard deviation of timings
    throughput_mbps : float
        Throughput in MB/second (based on mean)
    metadata : dict
        Additional metadata about the benchmark

    """

    format_name: str
    file_path: Path
    file_size: int
    iterations: int
    timings: List[float]
    mean_time: float
    median_time: float
    min_time: float
    max_time: float
    std_dev: float
    throughput_mbps: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization.

        Returns
        -------
        dict
            Dictionary representation of benchmark result

        """
        return {
            "format": self.format_name,
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "file_size_mb": round(self.file_size / (1024 * 1024), 2),
            "iterations": self.iterations,
            "timings": self.timings,
            "mean_time": self.mean_time,
            "median_time": self.median_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "std_dev": self.std_dev,
            "throughput_mbps": self.throughput_mbps,
            "mean_formatted": format_duration(self.mean_time),
            "metadata": self.metadata,
        }


class BenchmarkRunner:
    """Helper class for running and managing performance benchmarks.

    Parameters
    ----------
    warmup_iterations : int, default 1
        Number of warmup iterations before timing
    default_iterations : int, default 3
        Default number of timed iterations
    results_dir : Path, optional
        Directory to save results

    """

    def __init__(
        self, warmup_iterations: int = 1, default_iterations: int = 3, results_dir: Optional[Path] = None
    ) -> None:
        """Initialize the benchmark runner."""
        self.warmup_iterations = warmup_iterations
        self.default_iterations = default_iterations
        self.results_dir = results_dir or Path(__file__).parent / "results"
        self.results: List[BenchmarkResult] = []
        self.timer = OperationTimer()

    def run(
        self,
        format_name: str,
        file_path: Path,
        iterations: Optional[int] = None,
        conversion_func: Optional[Callable] = None,
        **conversion_kwargs: Any,
    ) -> BenchmarkResult:
        """Run a benchmark for a specific file.

        Parameters
        ----------
        format_name : str
            Name of the format being tested
        file_path : Path
            Path to the test file
        iterations : int, optional
            Number of iterations (uses default if not specified)
        conversion_func : callable, optional
            Conversion function to use (default: to_markdown)
        **conversion_kwargs
            Additional kwargs to pass to conversion function

        Returns
        -------
        BenchmarkResult
            Results from the benchmark run

        """
        if iterations is None:
            iterations = self.default_iterations

        if conversion_func is None:
            conversion_func = to_markdown

        file_size = file_path.stat().st_size
        timings: List[float] = []

        # Warmup iterations
        for _ in range(self.warmup_iterations):
            conversion_func(file_path, **conversion_kwargs)

        # Timed iterations
        for _ in range(iterations):
            start = time.perf_counter()
            conversion_func(file_path, **conversion_kwargs)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        # Calculate statistics
        mean_time = statistics.mean(timings)
        median_time = statistics.median(timings)
        min_time = min(timings)
        max_time = max(timings)
        std_dev = statistics.stdev(timings) if len(timings) > 1 else 0.0

        # Calculate throughput in MB/s
        throughput_mbps = (file_size / (1024 * 1024)) / mean_time if mean_time > 0 else 0.0

        # Get git commit if available
        metadata = self._get_metadata()

        result = BenchmarkResult(
            format_name=format_name,
            file_path=file_path,
            file_size=file_size,
            iterations=iterations,
            timings=timings,
            mean_time=mean_time,
            median_time=median_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            throughput_mbps=throughput_mbps,
            metadata=metadata,
        )

        self.results.append(result)
        return result

    def _get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the current environment.

        Returns
        -------
        dict
            Metadata dictionary

        """
        metadata = {
            "timestamp": datetime.now().isoformat(),
        }

        # Try to get git commit
        try:
            git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
            metadata["git_commit"] = git_hash[:8]
        except Exception:
            metadata["git_commit"] = "unknown"

        return metadata

    def print_summary(self) -> None:
        """Print a formatted summary of all benchmark results."""
        if not self.results:
            print("No benchmark results to display")
            return

        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS SUMMARY")
        print("=" * 80)
        print(f"{'Format':<12} {'File':<30} {'Size':<10} {'Mean':<12} {'Throughput':<15}")
        print("-" * 80)

        for result in self.results:
            file_name = result.file_path.name
            if len(file_name) > 28:
                file_name = file_name[:25] + "..."

            size_mb = result.file_size / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{result.file_size / 1024:.1f} KB"

            throughput_str = f"{result.throughput_mbps:.2f} MB/s"

            print(
                f"{result.format_name:<12} "
                f"{file_name:<30} "
                f"{size_str:<10} "
                f"{format_duration(result.mean_time):<12} "
                f"{throughput_str:<15}"
            )

        print("=" * 80 + "\n")

    def save_results_csv(self, filename: Optional[str] = None) -> Path:
        """Save benchmark results to CSV file.

        Parameters
        ----------
        filename : str, optional
            Custom filename (default: benchmark_results_<timestamp>.csv)

        Returns
        -------
        Path
            Path to the saved CSV file

        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.csv"

        self.results_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.results_dir / filename

        fieldnames = [
            "format",
            "file_path",
            "file_size",
            "file_size_mb",
            "iterations",
            "mean_time",
            "median_time",
            "min_time",
            "max_time",
            "std_dev",
            "throughput_mbps",
            "git_commit",
            "timestamp",
        ]

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in self.results:
                row_data = result.to_dict()
                # Filter to only include fieldnames
                row = {k: row_data.get(k, "") for k in fieldnames}
                row["git_commit"] = result.metadata.get("git_commit", "unknown")
                row["timestamp"] = result.metadata.get("timestamp", "")
                writer.writerow(row)

        return filepath

    def save_results_json(self, filename: Optional[str] = None) -> Path:
        """Save benchmark results to JSON file.

        Parameters
        ----------
        filename : str, optional
            Custom filename (default: benchmark_results_<timestamp>.json)

        Returns
        -------
        Path
            Path to the saved JSON file

        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"

        self.results_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.results_dir / filename

        data = {
            "benchmark_run": {
                "timestamp": datetime.now().isoformat(),
                "warmup_iterations": self.warmup_iterations,
                "default_iterations": self.default_iterations,
            },
            "results": [r.to_dict() for r in self.results],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return filepath


@pytest.fixture(scope="session")
def session_benchmark_runner() -> BenchmarkRunner:
    """Provide a session-wide BenchmarkRunner instance.

    Returns
    -------
    BenchmarkRunner
        Session-wide benchmark runner instance

    """
    return BenchmarkRunner()


@pytest.fixture
def benchmark_runner(request: pytest.FixtureRequest, session_benchmark_runner: BenchmarkRunner) -> BenchmarkRunner:
    """Provide a BenchmarkRunner instance for tests.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object
    session_benchmark_runner : BenchmarkRunner
        Session-wide benchmark runner

    Returns
    -------
    BenchmarkRunner
        Configured benchmark runner instance

    """
    return session_benchmark_runner


@pytest.fixture(scope="session", autouse=True)
def save_benchmark_results(request: pytest.FixtureRequest, session_benchmark_runner: BenchmarkRunner) -> None:
    """Save benchmark results to file after test session.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object
    session_benchmark_runner : BenchmarkRunner
        Session-wide benchmark runner

    """
    yield

    # Print summary and save results after all tests complete
    if session_benchmark_runner.results:
        session_benchmark_runner.print_summary()

        if request.config.getoption("--benchmark-save", default=False):
            csv_path = session_benchmark_runner.save_results_csv()
            json_path = session_benchmark_runner.save_results_json()
            print(f"\nBenchmark results saved to:")
            print(f"  CSV:  {csv_path}")
            print(f"  JSON: {json_path}")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for benchmarking.

    Parameters
    ----------
    parser : pytest.Parser
        Pytest parser for adding options

    """
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Run benchmark tests (marked with @pytest.mark.benchmark)",
    )
    parser.addoption(
        "--benchmark-save", action="store_true", default=False, help="Save benchmark results to CSV and JSON files"
    )
    parser.addoption(
        "--benchmark-iterations",
        action="store",
        type=int,
        default=3,
        help="Number of iterations for each benchmark (default: 3)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for benchmark tests.

    Parameters
    ----------
    config : pytest.Config
        Pytest configuration object

    """
    if not config.getoption("--benchmark"):
        setattr(config.option, "markexpr", "not benchmark")

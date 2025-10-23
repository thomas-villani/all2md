#!/usr/bin/env python3
"""Batch Document Converter with Progress UI.

This example demonstrates how to convert entire directory trees with rich
progress feedback, parallel processing, error handling, and resume capability.
It showcases the all2md progress callback system and concurrent processing.

Features
--------
- Convert entire directory trees recursively
- Rich progress bars and status updates
- Parallel processing for speed
- Comprehensive error handling and reporting
- Resume interrupted conversions
- Configurable output structure (mirror, flat, by-format)

Use Cases
---------
- Bulk conversions
- Migration projects
- Archive processing
- Content management
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from all2md import convert, registry
from all2md.progress import ProgressEvent


@dataclass
class ConversionJob:
    """A single file conversion job.

    Parameters
    ----------
    input_path : Path
        Input file path
    output_path : Path
        Output file path
    source_format : str or None, default = None
        Source format (auto-detected if None)
    target_format : str, default = "markdown"
        Target format
    status : str, default = "pending"
        Job status: pending, processing, completed, failed, skipped
    error : str or None, default = None
        Error message if failed

    """

    input_path: Path
    output_path: Path
    source_format: Optional[str] = None
    target_format: str = "markdown"
    status: str = "pending"
    error: Optional[str] = None


@dataclass
class BatchProgress:
    """Batch conversion progress tracking.

    Parameters
    ----------
    total_jobs : int, default = 0
        Total number of conversion jobs
    completed : int, default = 0
        Number of completed jobs
    failed : int, default = 0
        Number of failed jobs
    skipped : int, default = 0
        Number of skipped jobs
    current_file : str, default = ''
        Currently processing file

    """

    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    current_file: str = ""


@dataclass
class BatchConfig:
    """Configuration for batch conversion.

    Parameters
    ----------
    input_dir : Path
        Input directory
    output_dir : Path
        Output directory
    target_format : str, default = "markdown"
        Target output format
    recursive : bool, default = True
        Process subdirectories recursively
    output_structure : str, default = "mirror"
        Output structure: mirror, flat, by-format
    max_workers : int, default = 4
        Maximum parallel workers
    checkpoint_file : Path or None, default = None
        Checkpoint file for resume capability
    extensions : list of str or None, default = None
        File extensions to process (None = all supported)

    """

    input_dir: Path
    output_dir: Path
    target_format: str = "markdown"
    recursive: bool = True
    output_structure: str = "mirror"
    max_workers: int = 4
    checkpoint_file: Optional[Path] = None
    extensions: Optional[list[str]] = None


class BatchConverter:
    """Batch document converter with progress tracking.

    Parameters
    ----------
    config : BatchConfig
        Batch conversion configuration

    """

    def __init__(self, config: BatchConfig):
        """Initialize batch converter with configuration."""
        self.config = config
        self.progress = BatchProgress()
        self.jobs: list[ConversionJob] = []
        self.completed_jobs: set[str] = set()

        if config.checkpoint_file and config.checkpoint_file.exists():
            self._load_checkpoint()

    def _get_output_extension(self, format: str) -> str:
        """Get file extension for output format.

        Parameters
        ----------
        format : str
            Output format

        Returns
        -------
        str
            File extension

        """
        extensions = {
            "markdown": ".md",
            "html": ".html",
            "pdf": ".pdf",
            "docx": ".docx",
            "rst": ".rst",
            "asciidoc": ".adoc",
            "latex": ".tex",
        }
        return extensions.get(format, ".txt")

    def _get_output_path(self, input_path: Path) -> Path:
        """Calculate output path based on configuration.

        Parameters
        ----------
        input_path : Path
            Input file path

        Returns
        -------
        Path
            Output file path

        """
        ext = self._get_output_extension(self.config.target_format)

        if self.config.output_structure == "mirror":
            rel_path = input_path.relative_to(self.config.input_dir)
            output_path = self.config.output_dir / rel_path.parent / (rel_path.stem + ext)

        elif self.config.output_structure == "flat":
            safe_name = str(input_path.relative_to(self.config.input_dir)).replace(os.sep, "_")
            output_path = self.config.output_dir / (Path(safe_name).stem + ext)

        elif self.config.output_structure == "by-format":
            source_format = registry.detect_format(str(input_path))
            format_dir = self.config.output_dir / (source_format or "unknown")
            output_path = format_dir / (input_path.stem + ext)

        else:
            raise ValueError(f"Unknown output structure: {self.config.output_structure}")

        return output_path

    def _should_process_file(self, path: Path) -> bool:
        """Check if file should be processed.

        Parameters
        ----------
        path : Path
            File path to check

        Returns
        -------
        bool
            True if file should be processed

        """
        if not path.is_file():
            return False

        if self.config.extensions:
            return path.suffix.lower() in self.config.extensions

        return True

    def discover_jobs(self):
        """Discover all conversion jobs in input directory."""
        print(f"Discovering files in: {self.config.input_dir}")

        pattern = "**/*" if self.config.recursive else "*"
        all_paths = list(self.config.input_dir.glob(pattern))

        for input_path in all_paths:
            if not self._should_process_file(input_path):
                continue

            input_key = str(input_path.relative_to(self.config.input_dir))

            if input_key in self.completed_jobs:
                self.progress.skipped += 1
                continue

            output_path = self._get_output_path(input_path)

            job = ConversionJob(
                input_path=input_path,
                output_path=output_path,
                target_format=self.config.target_format,
            )
            self.jobs.append(job)

        self.progress.total_jobs = len(self.jobs)
        print(f"Found {self.progress.total_jobs} files to convert")
        if self.progress.skipped > 0:
            print(f"Skipping {self.progress.skipped} already completed files")

    def _convert_single_file(self, job: ConversionJob) -> ConversionJob:
        """Convert a single file.

        Parameters
        ----------
        job : ConversionJob
            Conversion job

        Returns
        -------
        ConversionJob
            Updated job with status

        """
        try:
            job.status = "processing"

            job.output_path.parent.mkdir(parents=True, exist_ok=True)

            def progress_callback(event: ProgressEvent):
                pass

            convert(
                str(job.input_path),
                output=str(job.output_path),
                target_format=job.target_format,
                progress_callback=progress_callback,
            )

            job.status = "completed"

        except Exception as e:
            job.status = "failed"
            job.error = str(e)

        return job

    def _save_checkpoint(self):
        """Save checkpoint of completed jobs."""
        if not self.config.checkpoint_file:
            return

        checkpoint_data = {
            "completed": list(self.completed_jobs),
            "progress": asdict(self.progress),
        }

        with open(self.config.checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

    def _load_checkpoint(self):
        """Load checkpoint of previously completed jobs."""
        if not self.config.checkpoint_file or not self.config.checkpoint_file.exists():
            return

        try:
            with open(self.config.checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)

            self.completed_jobs = set(checkpoint_data.get("completed", []))
            print(f"Loaded checkpoint: {len(self.completed_jobs)} completed files")

        except Exception as e:
            print(f"Warning: Failed to load checkpoint: {e}")

    def convert_all(self):
        """Convert all discovered files with progress tracking."""
        if not self.jobs:
            print("No files to convert")
            return

        print(f"\nStarting conversion with {self.config.max_workers} workers...")
        print("-" * 70)

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {executor.submit(self._convert_single_file, job): job for job in self.jobs}

            for future in as_completed(futures):
                job = future.result()

                if job.status == "completed":
                    self.progress.completed += 1
                    input_key = str(job.input_path.relative_to(self.config.input_dir))
                    self.completed_jobs.add(input_key)
                    status_icon = "OK"
                elif job.status == "failed":
                    self.progress.failed += 1
                    status_icon = "FAILED"
                else:
                    status_icon = "UNKNOWN"

                total = self.progress.total_jobs
                done = self.progress.completed + self.progress.failed
                percentage = (done / total * 100) if total > 0 else 0

                rel_path = job.input_path.relative_to(self.config.input_dir)
                print(f"[{done}/{total}] ({percentage:.1f}%) {status_icon:8} {rel_path}")

                if job.error:
                    print(f"         Error: {job.error[:60]}")

                if done % 10 == 0:
                    self._save_checkpoint()

        self._save_checkpoint()

    def print_summary(self):
        """Print conversion summary."""
        print("\n" + "=" * 70)
        print("Batch Conversion Summary")
        print("=" * 70)
        print(f"Total files: {self.progress.total_jobs}")
        print(f"Completed: {self.progress.completed}")
        print(f"Failed: {self.progress.failed}")
        print(f"Skipped: {self.progress.skipped}")

        if self.progress.failed > 0:
            print(f"\nFailed conversions: {self.progress.failed}")
            for job in self.jobs:
                if job.status == "failed":
                    print(f"  - {job.input_path.name}: {job.error}")

        print(f"\nOutput directory: {self.config.output_dir}")
        print("=" * 70)


def main():
    """Run the batch converter."""
    import argparse

    parser = argparse.ArgumentParser(description="Batch convert documents with progress tracking")
    parser.add_argument("input_dir", type=Path, help="Input directory")
    parser.add_argument("output_dir", type=Path, help="Output directory")
    parser.add_argument(
        "--format",
        "-f",
        default="markdown",
        help="Target format (default: markdown)",
    )
    parser.add_argument(
        "--structure",
        choices=["mirror", "flat", "by-format"],
        default="mirror",
        help="Output structure (default: mirror)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't process subdirectories",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Checkpoint file for resume capability",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        help="File extensions to process (e.g., .pdf .docx)",
    )

    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Error: Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    config = BatchConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        target_format=args.format,
        recursive=not args.no_recursive,
        output_structure=args.structure,
        max_workers=args.workers,
        checkpoint_file=args.checkpoint,
        extensions=args.extensions,
    )

    converter = BatchConverter(config)
    converter.discover_jobs()
    converter.convert_all()
    converter.print_summary()

    sys.exit(1 if converter.progress.failed > 0 else 0)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Batch Document Converter with Progress UI")
        print("=" * 70)
        print()
        print("Convert entire directory trees with rich progress feedback.")
        print()
        print("Usage:")
        print("  python batch_converter.py ./docs ./output")
        print("  python batch_converter.py ./pdfs ./markdown --format markdown")
        print("  python batch_converter.py ./files ./html --format html --workers 8")
        print()
        print("Features:")
        print("  - Recursive directory processing")
        print("  - Parallel processing for speed")
        print("  - Progress tracking and reporting")
        print("  - Error handling and recovery")
        print("  - Resume interrupted conversions")
        print("  - Flexible output organization")
        print()
        print("Options:")
        print("  --format FORMAT        Target format (default: markdown)")
        print("  --structure STYLE      Output structure:")
        print("                           mirror - preserve directory structure")
        print("                           flat - all files in output dir")
        print("                           by-format - organize by source format")
        print("  --workers N            Parallel workers (default: 4)")
        print("  --no-recursive         Don't process subdirectories")
        print("  --checkpoint FILE      Checkpoint file for resume")
        print("  --extensions EXT...    File extensions to process")
        print()
        print("Examples:")
        print("  Convert all PDFs to markdown:")
        print("    python batch_converter.py ./pdfs ./output --extensions .pdf")
        print()
        print("  Convert with 8 workers and checkpointing:")
        print("    python batch_converter.py ./docs ./html --format html \\")
        print("      --workers 8 --checkpoint ./checkpoint.json")
        print()
        print("  Organize output by source format:")
        print("    python batch_converter.py ./mixed ./output --structure by-format")
        print()
        sys.exit(0)

    main()

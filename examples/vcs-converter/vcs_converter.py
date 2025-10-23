"""Version Control System Document Converter.

This module provides functionality to make binary documents (DOCX, PPTX, PDF)
git-friendly by converting them to markdown for version control.

Features:
    - Convert binary formats to markdown for git tracking
    - Preserve formatting metadata
    - Bidirectional sync (markdown <-> binary)
    - Batch processing
    - Diff-friendly output
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import all2md
from all2md.ast import Document
from all2md.ast.serialization import ast_to_dict
from all2md.renderers.docx import DocxRenderer
from all2md.renderers.pdf import PdfRenderer

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class VCSConverter:
    """Converter for making binary documents version control friendly.

    Parameters
    ----------
    config_path : Path, optional
        Path to configuration file
    """

    BINARY_FORMATS = {".docx", ".pptx", ".pdf", ".doc", ".ppt"}
    MARKDOWN_SUFFIX = ".vcs.md"
    METADATA_SUFFIX = ".vcs.json"

    def __init__(self, config_path: Path | None = None) -> None:
        self.config = self._load_config(config_path)
        self.markdown_dir = Path(self.config.get("markdown_dir", ".vcs-docs"))
        self.track_metadata = self.config.get("track_metadata", True)
        self.preserve_images = self.config.get("preserve_images", True)
        self.line_width = self.config.get("line_width", 80)

    def _load_config(self, config_path: Path | None) -> dict[str, Any]:
        """Load configuration from file.

        Parameters
        ----------
        config_path : Path, optional
            Path to configuration file

        Returns
        -------
        dict[str, Any]
            Configuration dictionary
        """
        if config_path and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_markdown_path(self, binary_path: Path) -> Path:
        """Get the markdown path for a binary document.

        Parameters
        ----------
        binary_path : Path
            Path to binary document

        Returns
        -------
        Path
            Path where markdown should be stored
        """
        relative = binary_path.relative_to(Path.cwd()) if binary_path.is_absolute() else binary_path
        md_path = self.markdown_dir / relative.parent / (relative.stem + self.MARKDOWN_SUFFIX)
        return md_path

    def _get_metadata_path(self, binary_path: Path) -> Path:
        """Get the metadata path for a binary document.

        Parameters
        ----------
        binary_path : Path
            Path to binary document

        Returns
        -------
        Path
            Path where metadata should be stored
        """
        md_path = self._get_markdown_path(binary_path)
        return md_path.with_suffix(self.METADATA_SUFFIX)

    def convert_to_markdown(self, binary_path: Path) -> tuple[Path, Path | None]:
        """Convert a binary document to markdown.

        Parameters
        ----------
        binary_path : Path
            Path to binary document

        Returns
        -------
        tuple[Path, Path | None]
            Paths to created markdown and metadata files
        """
        logger.info(f"Converting {binary_path} to markdown...")

        md_path = self._get_markdown_path(binary_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to markdown with AST for metadata extraction
        with open(binary_path, "rb") as f:
            doc = all2md.to_markdown(
                f,
                filename=str(binary_path),
                return_ast=True,
            )

        # Extract markdown and metadata
        if isinstance(doc, Document):
            # Render to markdown
            from all2md.renderers.markdown import MarkdownRenderer

            renderer = MarkdownRenderer()
            markdown_content = renderer.render(doc)

            # Extract metadata
            metadata = None
            if self.track_metadata:
                metadata = self._extract_metadata(doc, binary_path)
        else:
            # String result
            markdown_content = doc
            metadata = None

        # Write markdown
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Write metadata if enabled
        metadata_path = None
        if self.track_metadata and metadata:
            metadata_path = self._get_metadata_path(binary_path)
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

        logger.info(f"Created: {md_path}")
        if metadata_path:
            logger.info(f"Created: {metadata_path}")

        return md_path, metadata_path

    def _extract_metadata(self, doc: Document, binary_path: Path) -> dict[str, Any]:
        """Extract metadata from document AST.

        Parameters
        ----------
        doc : Document
            Document AST
        binary_path : Path
            Path to original binary document

        Returns
        -------
        dict[str, Any]
            Document metadata
        """
        metadata = {
            "source_file": str(binary_path),
            "source_format": binary_path.suffix,
            "ast_version": "1.0",
        }

        # Extract document metadata if present
        if hasattr(doc, "metadata") and doc.metadata:
            metadata["document_metadata"] = doc.metadata

        # Store AST structure for perfect reconstruction
        if self.config.get("store_ast", False):
            metadata["ast"] = ast_to_dict(doc)

        return metadata

    def convert_to_binary(self, markdown_path: Path, output_path: Path | None = None) -> Path:
        """Convert markdown back to binary format.

        Parameters
        ----------
        markdown_path : Path
            Path to markdown file
        output_path : Path, optional
            Output path for binary document

        Returns
        -------
        Path
            Path to created binary document
        """
        # Load metadata to determine target format
        metadata_path = markdown_path.with_suffix(self.METADATA_SUFFIX)
        if not metadata_path.exists():
            raise ValueError(f"No metadata found for {markdown_path}")

        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)

        source_format = metadata.get("source_format", ".docx")

        if output_path is None:
            # Reconstruct original path
            source_file = Path(metadata["source_file"])
            output_path = source_file

        logger.info(f"Converting {markdown_path} to {source_format}...")

        # Read markdown
        with open(markdown_path, encoding="utf-8") as f:
            markdown_content = f.read()

        # Convert based on target format
        if source_format in {".docx", ".doc"}:
            self._markdown_to_docx(markdown_content, output_path, metadata)
        elif source_format == ".pdf":
            self._markdown_to_pdf(markdown_content, output_path, metadata)
        elif source_format in {".pptx", ".ppt"}:
            logger.warning("PPTX conversion from markdown not yet implemented")
            raise NotImplementedError("PPTX conversion not supported")
        else:
            raise ValueError(f"Unsupported target format: {source_format}")

        logger.info(f"Created: {output_path}")
        return output_path

    def _markdown_to_docx(self, markdown: str, output_path: Path, metadata: dict[str, Any]) -> None:
        """Convert markdown to DOCX format.

        Parameters
        ----------
        markdown : str
            Markdown content
        output_path : Path
            Output path for DOCX file
        metadata : dict[str, Any]
            Document metadata
        """
        # Parse markdown to AST
        doc = all2md.to_markdown(markdown, source_format="markdown", return_ast=True)

        # Render to DOCX
        renderer = DocxRenderer()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        renderer.render_to_file(doc, str(output_path))

    def _markdown_to_pdf(self, markdown: str, output_path: Path, metadata: dict[str, Any]) -> None:
        """Convert markdown to PDF format.

        Parameters
        ----------
        markdown : str
            Markdown content
        output_path : Path
            Output path for PDF file
        metadata : dict[str, Any]
            Document metadata
        """
        # Parse markdown to AST
        doc = all2md.to_markdown(markdown, source_format="markdown", return_ast=True)

        # Render to PDF
        renderer = PdfRenderer()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        renderer.render_to_file(doc, str(output_path))

    def scan_repository(self, root_dir: Path | None = None) -> list[Path]:
        """Scan repository for binary documents.

        Parameters
        ----------
        root_dir : Path, optional
            Root directory to scan

        Returns
        -------
        list[Path]
            List of binary document paths
        """
        if root_dir is None:
            root_dir = Path.cwd()

        binary_docs = []
        exclude_dirs = {".git", ".vcs-docs", "venv", ".venv", "node_modules", "__pycache__"}

        for path in root_dir.rglob("*"):
            if any(excluded in path.parts for excluded in exclude_dirs):
                continue
            if path.suffix.lower() in self.BINARY_FORMATS and path.is_file():
                binary_docs.append(path)

        return binary_docs

    def batch_convert(self, root_dir: Path | None = None, force: bool = False) -> None:
        """Convert all binary documents in repository.

        Parameters
        ----------
        root_dir : Path, optional
            Root directory to scan
        force : bool
            Force reconversion even if markdown exists
        """
        binary_docs = self.scan_repository(root_dir)

        logger.info(f"Found {len(binary_docs)} binary document(s)")

        for doc_path in binary_docs:
            md_path = self._get_markdown_path(doc_path)

            # Skip if markdown exists and is newer (unless force)
            if not force and md_path.exists():
                if md_path.stat().st_mtime > doc_path.stat().st_mtime:
                    logger.info(f"Skipping {doc_path} (already converted)")
                    continue

            try:
                self.convert_to_markdown(doc_path)
            except Exception as e:
                logger.error(f"Failed to convert {doc_path}: {e}")

    def clean(self, root_dir: Path | None = None) -> None:
        """Remove all generated markdown and metadata files.

        Parameters
        ----------
        root_dir : Path, optional
            Root directory
        """
        if root_dir is None:
            root_dir = Path.cwd()

        markdown_dir = root_dir / self.markdown_dir
        if markdown_dir.exists():
            logger.info(f"Removing {markdown_dir}...")
            shutil.rmtree(markdown_dir)
            logger.info("Cleaned all VCS markdown files")
        else:
            logger.info("No VCS markdown directory found")


def main() -> int:
    """Main entry point for VCS converter.

    Returns
    -------
    int
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Make binary documents version control friendly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all binary docs in repository
  python vcs_converter.py batch

  # Convert specific document
  python vcs_converter.py to-md document.docx

  # Convert markdown back to binary
  python vcs_converter.py to-binary .vcs-docs/document.vcs.md

  # Clean generated files
  python vcs_converter.py clean
        """,
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Batch convert command
    batch_parser = subparsers.add_parser("batch", help="Convert all binary documents")
    batch_parser.add_argument(
        "--root",
        type=Path,
        help="Root directory to scan",
    )
    batch_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconversion even if markdown exists",
    )

    # To-markdown command
    to_md_parser = subparsers.add_parser("to-md", help="Convert binary to markdown")
    to_md_parser.add_argument(
        "file",
        type=Path,
        help="Binary document to convert",
    )

    # To-binary command
    to_binary_parser = subparsers.add_parser("to-binary", help="Convert markdown to binary")
    to_binary_parser.add_argument(
        "file",
        type=Path,
        help="Markdown file to convert",
    )
    to_binary_parser.add_argument(
        "--output",
        type=Path,
        help="Output path for binary document",
    )

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Remove all generated markdown files")
    clean_parser.add_argument(
        "--root",
        type=Path,
        help="Root directory",
    )

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for binary documents")
    scan_parser.add_argument(
        "--root",
        type=Path,
        help="Root directory to scan",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    converter = VCSConverter(args.config)

    try:
        if args.command == "batch":
            converter.batch_convert(args.root, args.force)
        elif args.command == "to-md":
            converter.convert_to_markdown(args.file)
        elif args.command == "to-binary":
            converter.convert_to_binary(args.file, args.output)
        elif args.command == "clean":
            converter.clean(args.root)
        elif args.command == "scan":
            docs = converter.scan_repository(args.root)
            print(f"Found {len(docs)} binary document(s):")
            for doc in docs:
                print(f"  - {doc}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

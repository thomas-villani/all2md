"""Version Control System Document Converter.

Makes binary documents (DOCX, PPTX, PDF) git-friendly by maintaining parallel
markdown versions alongside them, so ``git diff`` shows prose instead of
``Binary files a/spec.docx and b/spec.docx differ``.

This is the *committed sidecar* approach: the generated markdown is checked in.
That is what makes ``git blame`` work and merge conflicts resolvable in text --
which git's ``textconv`` cannot do -- at the cost of duplicated content in the
repository. See README.md for when to prefer the alternatives.

Features:
    - Convert binary formats to markdown for git tracking
    - Preserve structured metadata alongside each document
    - Convert markdown back to a binary format (never in place by default)
    - Batch processing with content-hash change detection
    - Pre-commit hook integration that reads *staged* content
"""

import argparse
import fnmatch
import hashlib
import io
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import all2md
from all2md import roundtrippable_formats
from all2md.ast import Document
from all2md.ast.serialization import ast_to_dict

# Configure only this script's logger. Calling logging.basicConfig() would set
# the level on the *root* logger and surface all2md's own INFO records
# ("Starting pipeline execution", ...) in the middle of the hook's output.
logger = logging.getLogger("vcs_converter")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

_HASH_CHUNK = 65536


class VCSConverter:
    """Converter for making binary documents version control friendly.

    Parameters
    ----------
    config_path : Path, optional
        Path to configuration file
    root : Path, optional
        Repository root that document paths are resolved against. Defaults to
        the current working directory.

    """

    # Only formats all2md can actually parse. Legacy OLE formats (.doc, .ppt)
    # are deliberately absent: listing them made `scan` advertise files that
    # could never convert, and made the pre-commit hook abort *every* commit in
    # any repository that contained one. Check `all2md list-formats` before
    # adding to this set.
    BINARY_FORMATS = {".docx", ".pptx", ".pdf"}

    # Suffix -> all2md format name, used to ask the library what it can render.
    SUFFIX_TO_FORMAT = {".docx": "docx", ".pptx": "pptx", ".pdf": "pdf"}

    MARKDOWN_SUFFIX = ".vcs.md"
    METADATA_SUFFIX = ".vcs.json"

    def __init__(self, config_path: Path | None = None, root: Path | None = None) -> None:
        """Initialise the converter from *config_path*, resolving paths against *root*."""
        self.config = self._load_config(config_path)
        self.root = (root or Path.cwd()).resolve()
        self.markdown_dir = self.root / self.config.get("markdown_dir", ".vcs-docs")
        self.track_metadata = self.config.get("track_metadata", True)

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

    def _relative_to_root(self, path: Path) -> Path:
        """Return *path* relative to the configured root.

        Resolving against ``self.root`` rather than ``Path.cwd()`` is what makes
        ``--root`` and absolute paths work: keying off the working directory
        meant any document outside it failed with an opaque ``relative_to``
        error, which took out ``batch --root`` entirely.

        Parameters
        ----------
        path : Path
            Path to a document

        Returns
        -------
        Path
            Path relative to the root

        Raises
        ------
        ValueError
            If *path* lies outside the root

        """
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.root)
        except ValueError:
            raise ValueError(
                f"{resolved} is outside the repository root {self.root}. Pass --root to point at the repository."
            ) from None

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
        relative = self._relative_to_root(binary_path)
        return self.markdown_dir / relative.parent / (relative.stem + self.MARKDOWN_SUFFIX)

    def _metadata_path_for(self, md_path: Path) -> Path:
        """Metadata path for a generated markdown path.

        Swaps the markdown suffix (``.vcs.md``) for the metadata suffix
        (``.vcs.json``). Using ``Path.with_suffix`` here would only replace the
        trailing ``.md`` and yield ``*.vcs.vcs.json``.

        Parameters
        ----------
        md_path : Path
            Path to the generated markdown file

        Returns
        -------
        Path
            Path where metadata should be stored

        """
        if md_path.name.endswith(self.MARKDOWN_SUFFIX):
            return md_path.with_name(md_path.name[: -len(self.MARKDOWN_SUFFIX)] + self.METADATA_SUFFIX)
        return md_path.with_suffix(".json")

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
        return self._metadata_path_for(self._get_markdown_path(binary_path))

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        """Return the SHA-256 hex digest of *data*."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Return the SHA-256 hex digest of the file at *path*."""
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_HASH_CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _read_staged(self, binary_path: Path) -> bytes:
        """Read a document's *staged* content from the git index.

        The pre-commit hook must convert what is about to be committed, not what
        happens to be on disk. With partial staging (``git add -p``) or an
        unstaged edit, those differ, and converting the working tree silently
        commits markdown describing content that was never committed.

        Parameters
        ----------
        binary_path : Path
            Path to the document

        Returns
        -------
        bytes
            Staged file content

        Raises
        ------
        ValueError
            If the path has no staged content

        """
        relative = self._relative_to_root(binary_path).as_posix()
        result = subprocess.run(  # noqa: S603
            ["git", "show", f":{relative}"],  # noqa: S607
            capture_output=True,
            cwd=self.root,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise ValueError(f"No staged content for {relative}: {message}")
        return result.stdout

    def convert_to_markdown(self, binary_path: Path, staged: bool = False) -> tuple[Path, Path | None]:
        """Convert a binary document to markdown.

        Parameters
        ----------
        binary_path : Path
            Path to binary document
        staged : bool
            Read the content from the git index rather than the working tree

        Returns
        -------
        tuple[Path, Path | None]
            Paths to created markdown and metadata files

        """
        suffix = binary_path.suffix.lower()
        if suffix not in self.BINARY_FORMATS:
            raise ValueError(f"Unsupported format '{suffix}'. Supported: {', '.join(sorted(self.BINARY_FORMATS))}")

        logger.info(f"Converting {binary_path}{' (staged)' if staged else ''} to markdown...")

        content = self._read_staged(binary_path) if staged else binary_path.read_bytes()

        md_path = self._get_markdown_path(binary_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)

        # Parse to the AST once so we can both render markdown and capture
        # structured metadata from the same parse.
        doc = all2md.to_ast(io.BytesIO(content), source_format=suffix.lstrip("."))

        # Render the AST to markdown (text formats return a str).
        markdown_content = all2md.from_ast(doc, "markdown")
        if not isinstance(markdown_content, str):  # pragma: no cover - defensive
            raise TypeError(f"Expected markdown renderer to return str, got {type(markdown_content).__name__}")

        metadata = None
        if self.track_metadata:
            metadata = self._extract_metadata(doc, binary_path, self._hash_bytes(content))

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        metadata_path = None
        if metadata:
            metadata_path = self._get_metadata_path(binary_path)
            with open(metadata_path, "w", encoding="utf-8") as f:
                # default=str so a stray datetime in document metadata degrades
                # to a string rather than aborting the commit.
                json.dump(metadata, f, indent=2, default=str)

        logger.info(f"Created: {md_path}")
        if metadata_path:
            logger.info(f"Created: {metadata_path}")

        return md_path, metadata_path

    def _extract_metadata(self, doc: Document, binary_path: Path, source_hash: str) -> dict[str, Any]:
        """Extract metadata from document AST.

        Parameters
        ----------
        doc : Document
            Document AST
        binary_path : Path
            Path to original binary document
        source_hash : str
            SHA-256 of the source bytes that produced this markdown

        Returns
        -------
        dict[str, Any]
            Document metadata

        """
        metadata: dict[str, Any] = {
            # Stored root-relative so the sidecar stays valid in every clone,
            # regardless of where the repository sits on disk.
            "source_file": self._relative_to_root(binary_path).as_posix(),
            "source_format": binary_path.suffix.lower(),
            "source_sha256": source_hash,
            "ast_version": "1.0",
        }

        if getattr(doc, "metadata", None):
            metadata["document_metadata"] = doc.metadata

        # Off by default on purpose: a serialised AST is a large, churn-heavy
        # blob in a file whose entire point is to produce readable diffs.
        if self.config.get("store_ast", False):
            metadata["ast"] = ast_to_dict(doc)

        return metadata

    def convert_to_binary(
        self,
        markdown_path: Path,
        output_path: Path | None = None,
        in_place: bool = False,
    ) -> Path:
        """Convert markdown back to its original binary format.

        By default this writes a *new* file next to the original
        (``report.rebuilt.docx``) rather than overwriting it. Rendering markdown
        back to DOCX/PDF/PPTX cannot restore what markdown never carried --
        styles, images, layout, tracked changes, embedded objects -- so writing
        over the source silently destroys it. Pass ``in_place`` to accept that.

        Parameters
        ----------
        markdown_path : Path
            Path to markdown file
        output_path : Path, optional
            Explicit output path for the binary document
        in_place : bool
            Overwrite the original document instead of writing a copy

        Returns
        -------
        Path
            Path to created binary document

        """
        metadata_path = self._metadata_path_for(markdown_path)
        if not metadata_path.exists():
            raise ValueError(f"No metadata found for {markdown_path}")

        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)

        source_format = metadata.get("source_format", ".docx")
        target = self.SUFFIX_TO_FORMAT.get(source_format)
        if target is None:
            raise ValueError(f"Unsupported target format: {source_format}")

        # Ask the library what it can render rather than hardcoding a list. The
        # previous hardcoded "PPTX not supported" outlived the renderer that
        # made it untrue.
        if target not in roundtrippable_formats():
            raise ValueError(
                f"all2md cannot render back to {target} in this installation. "
                f"Run 'all2md list-formats' to see what is available."
            )

        source_file = Path(metadata["source_file"])
        if not source_file.is_absolute():
            source_file = self.root / source_file

        if output_path is None:
            if in_place:
                output_path = source_file
                logger.warning(
                    f"Overwriting {output_path} in place. Formatting the markdown could not carry "
                    f"(styles, images, layout, tracked changes) will be lost."
                )
            else:
                output_path = source_file.with_name(f"{source_file.stem}.rebuilt{source_file.suffix}")

        logger.info(f"Converting {markdown_path} to {source_format}...")

        markdown_content = markdown_path.read_text(encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        all2md.from_markdown(markdown_content, target, output=str(output_path))

        logger.info(f"Created: {output_path}")
        return output_path

    def scan_repository(self) -> list[Path]:
        """Scan the repository root for binary documents.

        Returns
        -------
        list[Path]
            List of binary document paths

        """
        binary_docs = []
        exclude_dirs = {".git", ".vcs-docs", "venv", ".venv", "node_modules", "__pycache__"}
        exclude_patterns = self.config.get("exclude_patterns", [])

        for path in self.root.rglob("*"):
            if any(excluded in path.parts for excluded in exclude_dirs):
                continue
            # Honour user-supplied glob patterns (match the bare name and the
            # full path, so both "~$*.docx" and "**/build/**" work).
            posix_path = path.as_posix()
            if any(fnmatch.fnmatch(path.name, pat) or fnmatch.fnmatch(posix_path, pat) for pat in exclude_patterns):
                continue
            if path.suffix.lower() in self.BINARY_FORMATS and path.is_file():
                binary_docs.append(path)

        return binary_docs

    def _is_unchanged(self, doc_path: Path, md_path: Path) -> bool:
        """Return True when *doc_path* already has up-to-date generated markdown.

        Compares a stored content hash rather than modification times. Git does
        not preserve mtimes, so after a clone every file carries its checkout
        time in arbitrary order -- an mtime comparison would skip documents that
        genuinely changed and reconvert ones that did not.

        Parameters
        ----------
        doc_path : Path
            Path to the binary document
        md_path : Path
            Path to its generated markdown

        Returns
        -------
        bool
            True if conversion can be skipped

        """
        if not md_path.exists():
            return False
        metadata_path = self._metadata_path_for(md_path)
        if not metadata_path.exists():
            return False
        try:
            with open(metadata_path, encoding="utf-8") as f:
                stored = json.load(f).get("source_sha256")
        except (OSError, json.JSONDecodeError):
            return False
        return bool(stored) and stored == self._hash_file(doc_path)

    def batch_convert(self, force: bool = False) -> int:
        """Convert all binary documents under the repository root.

        Parameters
        ----------
        force : bool
            Force reconversion even if the markdown is up to date

        Returns
        -------
        int
            Number of documents that failed to convert

        """
        binary_docs = self.scan_repository()
        logger.info(f"Found {len(binary_docs)} binary document(s)")

        failures = 0
        for doc_path in binary_docs:
            if not force and self._is_unchanged(doc_path, self._get_markdown_path(doc_path)):
                logger.info(f"Skipping {doc_path} (unchanged)")
                continue
            try:
                self.convert_to_markdown(doc_path)
            except Exception as e:
                logger.error(f"Failed to convert {doc_path}: {e}")
                failures += 1

        return failures

    def clean(self) -> None:
        """Remove all generated markdown and metadata files."""
        if self.markdown_dir.exists():
            logger.info(f"Removing {self.markdown_dir}...")
            shutil.rmtree(self.markdown_dir)
            logger.info("Cleaned all VCS markdown files")
        else:
            logger.info("No VCS markdown directory found")


def main() -> int:
    """Run the VCS converter command line interface.

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

  # Convert the *staged* version (what pre-commit hooks should do)
  python vcs_converter.py to-md document.docx --staged

  # Rebuild a binary alongside the original (document.rebuilt.docx)
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
    parser.add_argument(
        "--root",
        type=Path,
        help="Repository root that document paths resolve against (default: current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    batch_parser = subparsers.add_parser("batch", help="Convert all binary documents")
    batch_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconversion even if the generated markdown is up to date",
    )

    to_md_parser = subparsers.add_parser("to-md", help="Convert binary to markdown")
    to_md_parser.add_argument(
        "file",
        type=Path,
        help="Binary document to convert",
    )
    to_md_parser.add_argument(
        "--staged",
        action="store_true",
        help="Convert the staged content from the git index rather than the working tree",
    )

    to_binary_parser = subparsers.add_parser("to-binary", help="Convert markdown back to a binary format")
    to_binary_parser.add_argument(
        "file",
        type=Path,
        help="Markdown file to convert",
    )
    to_binary_parser.add_argument(
        "--output",
        type=Path,
        help="Output path for the binary document (default: alongside the original, named *.rebuilt.*)",
    )
    to_binary_parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the original document. Destroys anything markdown could not carry.",
    )

    subparsers.add_parser("clean", help="Remove all generated markdown files")
    subparsers.add_parser("scan", help="Scan for binary documents")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    converter = VCSConverter(args.config, root=args.root)

    try:
        if args.command == "batch":
            return 1 if converter.batch_convert(args.force) else 0
        if args.command == "to-md":
            # Generated paths go to stdout (logs go to stderr) so the
            # pre-commit hook can stage exactly these files instead of
            # blanket-adding the whole output directory.
            for path in converter.convert_to_markdown(args.file, staged=args.staged):
                if path is not None:
                    print(path)
        elif args.command == "to-binary":
            converter.convert_to_binary(args.file, args.output, in_place=args.in_place)
        elif args.command == "clean":
            converter.clean()
        elif args.command == "scan":
            docs = converter.scan_repository()
            print(f"Found {len(docs)} binary document(s):")
            for doc in docs:
                print(f"  - {doc}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

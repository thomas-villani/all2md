"""The documents the viewer's file tree offers, found on disk.

``collect`` turns what was given to ``all2md read`` (directories, files, glob
patterns) into a ``FileTree``: the files all2md can read, below one root
directory. It walks without following symlinked directories, skips hidden
files and folders and the usual tool folders (``node_modules``,
``__pycache__``...), and stops at ``limit`` files. ``FileTree.nodes`` gives
the tree for Wijjit's ``Tree``, folders first.

Nothing here needs Wijjit, so it is tested without it.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

#: Folders never walked into (hidden ones are skipped as well).
SKIP_DIRS = frozenset({"node_modules", "__pycache__", "site-packages", "venv"})

#: The most files a tree holds; a walk stops there.
MAX_FILES = 5000

_GLOB_CHARS = frozenset("*?[")


@dataclass(frozen=True)
class FileTree:
    """Readable files below a root directory.

    Attributes
    ----------
    root : Path
        The directory the tree shows, absolute.
    files : tuple of Path
        The files, absolute (a symlinked file keeps its own path), sorted by their path below ``root``.
    truncated : bool
        True when the walk stopped at the file limit.

    """

    root: Path
    files: tuple[Path, ...]
    truncated: bool = False

    def node_id(self, path: Path) -> str:
        """Return the tree node id of a file (its path below the root)."""
        return "f:" + path.relative_to(self.root).as_posix()

    def path_of(self, node_id: str) -> Optional[Path]:
        """Return the file a node id names, or None for a folder or an unknown id."""
        if not node_id.startswith("f:"):
            return None
        path = self.root / node_id[2:]
        return path if path in self._file_set else None

    def folder_ids(self, path: Optional[Path] = None) -> list[str]:
        """Return the node ids of the folders above ``path``, or of every folder."""
        if path is None:
            folders = {parent for file in self.files for parent in self._parents(file)}
            return sorted(folders)
        return self._parents(path)

    def nodes(self) -> list[dict[str, Any]]:
        """Return the tree as Wijjit tree nodes: folders first, then files, each by name."""
        top: dict[str, Any] = {}
        for file in self.files:
            level = top
            for part in file.relative_to(self.root).parts[:-1]:
                level = level.setdefault(part + "/", {})
            level[file.name] = file
        return _to_nodes(top, "")

    @cached_property
    def _file_set(self) -> frozenset[Path]:
        return frozenset(self.files)

    def _parents(self, file: Path) -> list[str]:
        parts = file.relative_to(self.root).parts[:-1]
        return ["d:" + "/".join(parts[: i + 1]) for i in range(len(parts))]


def collect(inputs: Sequence[str], limit: int = MAX_FILES) -> FileTree:
    """Collect the readable files named by ``inputs``.

    Parameters
    ----------
    inputs : sequence of str
        Directories (walked), files (kept whatever their extension) and glob
        patterns (``docs/**/*.md``; ``**`` crosses folders). None means the
        current directory.
    limit : int, default MAX_FILES
        Stop after this many files.

    Returns
    -------
    FileTree
        Rooted at the one directory given, otherwise at the folder that holds
        every file found.

    Raises
    ------
    FileNotFoundError
        If an input is neither an existing path nor a pattern.

    """
    readable = _readable_extensions()
    sources = list(inputs) or ["."]
    found: dict[Path, None] = {}
    truncated = False
    for source in sources:
        for path in _expand(source, readable):
            if len(found) >= limit:
                truncated = True
                break
            found.setdefault(_absolute(path), None)
        if truncated:
            break

    if len(sources) == 1 and Path(sources[0]).is_dir():
        root = _absolute(Path(sources[0]))
    elif found:
        root = Path(os.path.commonpath([path.parent for path in found]))
    else:
        root = _absolute(Path.cwd())
    files = sorted(found, key=lambda path: [part.lower() for part in path.relative_to(root).parts])
    return FileTree(root=root, files=tuple(files), truncated=truncated)


def _expand(source: str, readable: frozenset[str]) -> Iterator[Path]:
    """Yield the files one input names."""
    path = Path(source)
    if path.is_file():
        yield path  # named on purpose: kept whatever its extension
    elif path.is_dir():
        yield from _walk(path, readable)
    elif _GLOB_CHARS & set(source):
        for match in sorted(glob.glob(source, recursive=True)):
            matched = Path(match)
            if matched.is_dir():
                yield from _walk(matched, readable)
            elif matched.is_file() and _is_readable(matched.name, readable):
                yield matched
    else:
        raise FileNotFoundError(f"No such file or folder: {source}")


def _walk(top: Path, readable: frozenset[str]) -> Iterator[Path]:
    """Yield the readable files below ``top``, without entering hidden, tool or symlinked folders."""
    for folder, dirnames, filenames in os.walk(top, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith(".") and name not in SKIP_DIRS)
        for name in sorted(filenames):
            if not name.startswith(".") and _is_readable(name, readable):
                yield Path(folder) / name


def _is_readable(name: str, readable: frozenset[str]) -> bool:
    from all2md.converter_registry import match_extension

    return match_extension(name, readable) is not None


def _readable_extensions() -> frozenset[str]:
    from all2md.converter_registry import registry

    return frozenset(extension.lower() for extension in registry.get_all_extensions())


def _to_nodes(level: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    folders = sorted((name for name in level if name.endswith("/")), key=str.lower)
    files = sorted((name for name in level if not name.endswith("/")), key=str.lower)
    nodes = []
    for name in folders:
        path = prefix + name[:-1]
        nodes.append({"id": "d:" + path, "label": name, "children": _to_nodes(level[name], path + "/")})
    for name in files:
        nodes.append({"id": "f:" + prefix + name, "label": name, "children": []})
    return nodes


def _absolute(path: Path) -> Path:
    """Make ``path`` absolute and normal without resolving symlinks, so a linked file stays in its folder."""
    return Path(os.path.abspath(path))

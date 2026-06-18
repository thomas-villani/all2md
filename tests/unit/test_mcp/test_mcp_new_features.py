#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for MCP path resolution, list_workspace_files, and config additions."""

from pathlib import Path

import pytest

from all2md.mcp.config import MCPConfig, _parse_dir_list, load_config_from_env
from all2md.mcp.query_tools import list_workspace_files_impl
from all2md.mcp.schemas import ListWorkspaceFilesInput
from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs, resolve_workspace_path
from all2md.mcp.tools import _detect_source_type


def _read_cfg(*dirs):
    return MCPConfig(read_allowlist=prepare_allowlist_dirs([str(d) for d in dirs]))


@pytest.mark.unit
class TestWorkspaceRelativeResolution:
    """resolve_workspace_path and path detection treat the workspace as cwd."""

    def test_resolve_relative_against_workspace(self, tmp_path):
        (tmp_path / "report.md").write_text("# Hi")
        resolved = resolve_workspace_path("report.md", [tmp_path], must_exist=True)
        assert resolved is not None
        assert resolved.resolve() == (tmp_path / "report.md").resolve()

    def test_resolve_missing_returns_none(self, tmp_path):
        assert resolve_workspace_path("nope.md", [tmp_path], must_exist=True) is None

    def test_resolve_write_anchors_to_first_dir(self, tmp_path):
        resolved = resolve_workspace_path("out.docx", [tmp_path], must_exist=False)
        assert resolved == tmp_path / "out.docx"

    def test_bare_filename_detected_as_path(self, tmp_path):
        target = tmp_path / "doc.md"
        target.write_text("# Title\n\nBody.")
        source, kind = _detect_source_type("doc.md", _read_cfg(tmp_path))
        assert kind == "path"
        assert Path(source).resolve() == target.resolve()

    def test_workspace_relative_subpath_detected(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        target = sub / "doc.md"
        target.write_text("# Title")
        source, kind = _detect_source_type("sub/doc.md", _read_cfg(tmp_path))
        assert kind == "path"
        assert Path(source).resolve() == target.resolve()


@pytest.mark.unit
class TestSilentFailureFix:
    """A definite-but-missing path raises instead of being treated as text."""

    def test_missing_bare_filename_raises(self, tmp_path):
        with pytest.raises(MCPSecurityError, match="File not found"):
            _detect_source_type("missing.pdf", _read_cfg(tmp_path))

    def test_missing_relative_path_raises(self, tmp_path):
        with pytest.raises(MCPSecurityError, match="File not found"):
            _detect_source_type("subdir/missing.docx", _read_cfg(tmp_path))

    def test_inline_markdown_not_treated_as_path(self, tmp_path):
        # Prose with a dotted token but spaces is content, not a path.
        source, kind = _detect_source_type("See section 1.2 for details.", _read_cfg(tmp_path))
        assert kind == "plain_text"

    def test_inline_heading_not_treated_as_path(self, tmp_path):
        source, kind = _detect_source_type("# Title\n\nSome body text.", _read_cfg(tmp_path))
        assert kind == "plain_text"

    def test_html_still_inline(self, tmp_path):
        source, kind = _detect_source_type("<h1>Hi</h1>", _read_cfg(tmp_path))
        assert kind == "plain_text"


@pytest.mark.unit
class TestListWorkspaceFiles:
    """list_workspace_files lists only allowed files."""

    def test_lists_files_recursively(self, tmp_path):
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.pdf").write_text("b")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.docx").write_text("c")
        out = list_workspace_files_impl(ListWorkspaceFilesInput(), _read_cfg(tmp_path))
        names = {Path(f["path"]).name for f in out.files}
        assert names == {"a.md", "b.pdf", "c.docx"}
        assert out.total == 3
        assert out.truncated is False
        assert all("size_bytes" in f for f in out.files)

    def test_pattern_filter(self, tmp_path):
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.pdf").write_text("b")
        out = list_workspace_files_impl(ListWorkspaceFilesInput(pattern="*.pdf"), _read_cfg(tmp_path))
        names = {Path(f["path"]).name for f in out.files}
        assert names == {"b.pdf"}

    def test_non_recursive(self, tmp_path):
        (tmp_path / "a.md").write_text("a")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("c")
        out = list_workspace_files_impl(ListWorkspaceFilesInput(recursive=False), _read_cfg(tmp_path))
        names = {Path(f["path"]).name for f in out.files}
        assert names == {"a.md"}

    def test_subdirectory_scope(self, tmp_path):
        (tmp_path / "a.md").write_text("a")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("c")
        out = list_workspace_files_impl(ListWorkspaceFilesInput(subdirectory="sub"), _read_cfg(tmp_path))
        names = {Path(f["path"]).name for f in out.files}
        assert names == {"c.md"}

    def test_subdirectory_outside_allowlist_raises(self, tmp_path):
        allowed = tmp_path / "allowed"
        outside = tmp_path / "outside"
        allowed.mkdir()
        outside.mkdir()
        with pytest.raises(MCPSecurityError):
            list_workspace_files_impl(ListWorkspaceFilesInput(subdirectory=str(outside)), _read_cfg(allowed))

    def test_reports_read_dirs(self, tmp_path):
        out = list_workspace_files_impl(ListWorkspaceFilesInput(), _read_cfg(tmp_path))
        assert any(str(tmp_path.resolve()) == str(Path(d).resolve()) for d in out.read_dirs)


@pytest.mark.unit
class TestConfigAdditions:
    """Additional read dirs and the list-files toggle."""

    def test_parse_dir_list_separators(self):
        assert _parse_dir_list("a;b") == ["a", "b"]
        assert _parse_dir_list("a\nb\nc") == ["a", "b", "c"]
        assert _parse_dir_list("  ") is None
        assert _parse_dir_list(None) is None

    def test_parse_dir_list_ignores_unsubstituted_placeholder(self):
        # Hosts that leave an optional config blank may pass the raw placeholder.
        assert _parse_dir_list("${user_config.additional_read_dirs}") is None

    def test_additional_read_dirs_appended(self, tmp_path, monkeypatch):
        ws = tmp_path / "ws"
        extra = tmp_path / "extra"
        ws.mkdir()
        extra.mkdir()
        monkeypatch.setenv("ALL2MD_MCP_ALLOWED_READ_DIRS", str(ws))
        monkeypatch.setenv("ALL2MD_MCP_ALLOWED_WRITE_DIRS", str(ws))
        monkeypatch.setenv("ALL2MD_MCP_ADDITIONAL_READ_DIRS", str(extra))
        cfg = load_config_from_env()
        read = [str(p) for p in cfg.read_allowlist]
        write = [str(p) for p in cfg.write_allowlist]
        assert str(ws) in read and str(extra) in read
        # Additional dirs are read-only: never added to the write allowlist.
        assert str(extra) not in write

    def test_enable_list_files_env_toggle(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_MCP_ENABLE_LIST_FILES", "false")
        cfg = load_config_from_env()
        assert cfg.enable_list_files is False

"""Consistency checks for ``server.json``, the MCP registry entry.

Registry clients never run our launch instructions; they assemble
``uvx <runtimeArguments> all2md@<version> <packageArguments>`` from this file. A
version or extras set that drifts from the release installs a different server
than the one we tested, and nothing in a normal release would notice.
"""

import json
import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.unit


def _load_server_json() -> dict:
    return json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))


def _project_version() -> str:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def _pypi_package(server: dict) -> dict:
    (package,) = [p for p in server["packages"] if p["registryType"] == "pypi"]
    return package


def _with_requirement(package: dict) -> str:
    (arg,) = [a for a in package["runtimeArguments"] if a.get("name") == "--with"]
    return arg["value"]


def test_versions_match_the_release():
    server = _load_server_json()
    package = _pypi_package(server)
    version = _project_version()

    assert server["version"] == version
    assert package["version"] == version
    assert _with_requirement(package).endswith(f"=={version}")


def test_launches_the_mcp_subcommand_of_all2md():
    package = _pypi_package(_load_server_json())

    assert package["identifier"] == "all2md"
    assert package["runtimeHint"] == "uvx"
    assert [a["value"] for a in package["packageArguments"]] == ["mcp"]
    assert package["transport"] == {"type": "stdio"}


def _project_extras() -> dict[str, list[str]]:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["optional-dependencies"]


def test_both_install_routes_install_the_mcp_extra():
    """The registry entry and the .mcpb bundle install one extra, so they cannot drift apart."""
    requirement = _with_requirement(_pypi_package(_load_server_json()))
    with open(REPO_ROOT / "mcpb" / "pyproject.toml", "rb") as f:
        bundle_dependencies = tomllib.load(f)["project"]["dependencies"]

    assert requirement.startswith("all2md[mcp]==")
    assert [d for d in bundle_dependencies if d.startswith("all2md")] == [f"all2md[mcp]>={_project_version()}"]


def test_mcp_extra_brings_what_the_server_needs():
    """`all2md[mcp]` alone must give a server that reads documents and searches by default."""
    extras = _project_extras()
    mcp = extras["mcp"]
    names = {re.split(r"[<>=\[;]", r, maxsplit=1)[0].strip() for r in mcp}
    (self_reference,) = [r for r in mcp if r.startswith("all2md[")]
    formats = set(re.match(r"all2md\[([^\]]+)\]", self_reference).group(1).split(","))

    assert {"fastmcp", "rank-bm25"} <= names  # search_documents defaults to BM25 keyword mode
    assert {"pdf", "docx", "pptx", "xlsx", "html", "markdown"} <= formats
    assert formats <= set(extras), formats - set(extras)
    assert "pdf_layout" not in formats  # Polyform Noncommercial, kept out as it is from `all`


def test_readme_carries_the_ownership_marker():
    """The registry verifies PyPI ownership by finding ``mcp-name: <name>`` in the README."""
    name = _load_server_json()["name"]
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert re.search(rf"mcp-name: {re.escape(name)}(\s|-->)", readme)

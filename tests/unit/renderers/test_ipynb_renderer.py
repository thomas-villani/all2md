"""Unit tests for the IpynbRenderer."""

from __future__ import annotations

import json

import pytest

from all2md.options.ipynb import IpynbRendererOptions
from all2md.parsers.ipynb import IpynbToAstConverter
from all2md.renderers.ipynb import IpynbRenderer


def _round_trip_notebook(notebook: dict, renderer_options: IpynbRendererOptions | None = None) -> dict:
    """Helper to convert notebook -> AST -> notebook dict."""
    parser = IpynbToAstConverter()
    document = parser.convert_to_ast(notebook, "python")
    renderer = IpynbRenderer(renderer_options)
    rendered = renderer.render_to_string(document)
    return json.loads(rendered)


def test_code_cell_round_trip_preserves_source_and_outputs() -> None:
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12.0",
            },
        },
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 3,
                "metadata": {"trusted": True},
                "source": ["print('hello world')\n"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": ["hello world\n"],
                    }
                ],
            }
        ],
    }

    rendered = _round_trip_notebook(notebook)

    assert rendered["nbformat"] == 4
    assert rendered["nbformat_minor"] == 5
    assert rendered["cells"][0]["cell_type"] == "code"
    assert rendered["cells"][0]["source"] == notebook["cells"][0]["source"]
    assert rendered["cells"][0]["outputs"] == notebook["cells"][0]["outputs"]


def test_markdown_attachments_preserved() -> None:
    attachment_data = "iVBORw0KGgo="
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "attachments": {
                    "image.png": {
                        "image/png": attachment_data,
                    }
                },
                "source": ["![alt text](attachment:image.png)\n"],
            }
        ],
    }

    rendered = _round_trip_notebook(notebook)
    cell = rendered["cells"][0]

    assert cell["cell_type"] == "markdown"
    assert cell.get("attachments") == notebook["cells"][0]["attachments"]
    assert cell["source"] == notebook["cells"][0]["source"]


@pytest.mark.parametrize("include_trusted, include_ui", [(False, False), (True, True)])
def test_metadata_gating(include_trusted: bool, include_ui: bool) -> None:
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {
                    "trusted": True,
                    "collapsed": True,
                    "custom_key": "value",
                },
                "source": ["1 + 1\n"],
                "outputs": [],
            }
        ],
    }

    options = IpynbRendererOptions(
        include_trusted_metadata=include_trusted,
        include_ui_metadata=include_ui,
    )

    rendered = _round_trip_notebook(notebook, renderer_options=options)
    cell_meta = rendered["cells"][0]["metadata"]

    if include_trusted:
        assert cell_meta.get("trusted") is True
    else:
        assert "trusted" not in cell_meta

    if include_ui:
        assert cell_meta.get("collapsed") is True
    else:
        assert "collapsed" not in cell_meta

    # Unknown metadata should always be preserved by default
    assert cell_meta.get("custom_key") == "value"


def test_raw_cell_round_trip() -> None:
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "raw",
                "metadata": {"format": "latex"},
                "source": ["\\LaTeX raw cell\n"],
            }
        ],
    }

    rendered = _round_trip_notebook(notebook)

    assert rendered["cells"][0]["cell_type"] == "raw"
    assert rendered["cells"][0]["metadata"].get("format") == "latex"
    assert rendered["cells"][0]["source"] == notebook["cells"][0]["source"]

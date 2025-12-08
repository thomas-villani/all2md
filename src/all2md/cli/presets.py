#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Configuration presets for all2md CLI.

This module defines preset configurations for common use cases like fast
processing, high quality output, minimal text extraction, etc.
"""

from typing import Any, Dict

from all2md.cli.config import merge_configs

# Preset definitions
PRESETS: Dict[str, Dict[str, Any]] = {
    "fast": {
        "description": "Fast processing optimized for speed over quality",
        "config": {
            "attachment_mode": "skip",
            "pdf": {
                "skip_image_extraction": True,
                "detect_columns": False,
                "enable_table_fallback_detection": False,
            },
            "html": {
                "strip_dangerous_elements": True,
            },
            "pptx": {
                "include_notes": False,
            },
        },
    },
    "quality": {
        "description": "High quality processing with maximum fidelity",
        "config": {
            "attachment_mode": "save",
            "pdf": {
                "detect_columns": True,
                "enable_table_fallback_detection": True,
                "merge_hyphenated_words": True,
            },
            "html": {
                "strip_dangerous_elements": False,
                "extract_title": True,
            },
            "pptx": {
                "include_notes": True,
                "slide_numbers": True,
            },
            "epub": {
                "merge_chapters": True,
                "include_toc": True,
            },
        },
    },
    "minimal": {
        "description": "Text-only output with no attachments or images",
        "config": {
            "attachment_mode": "skip",
            "markdown": {
                "emphasis_symbol": "*",
            },
            "pdf": {
                "skip_image_extraction": True,
            },
            "html": {
                "strip_dangerous_elements": True,
            },
        },
    },
    "complete": {
        "description": "Complete preservation with all content and metadata",
        "config": {
            "attachment_mode": "save",
            "pdf": {
                "detect_columns": True,
                "enable_table_fallback_detection": True,
            },
            "html": {
                "extract_title": True,
                "network": {
                    "allow_remote_fetch": True,
                    "require_https": True,
                },
            },
            "pptx": {
                "include_notes": True,
                "slide_numbers": True,
            },
            "epub": {
                "merge_chapters": True,
                "include_toc": True,
            },
            "eml": {
                "include_headers": True,
                "preserve_thread_structure": True,
            },
        },
    },
    "archival": {
        "description": "Self-contained documents with embedded resources",
        "config": {
            "attachment_mode": "base64",
            "pdf": {
                "detect_columns": True,
                "merge_hyphenated_words": True,
            },
            "html": {
                "extract_title": True,
            },
            "epub": {
                "merge_chapters": True,
                "include_toc": True,
            },
        },
    },
    "documentation": {
        "description": "Optimized for technical documentation",
        "config": {
            "attachment_mode": "save",
            "markdown": {
                "emphasis_symbol": "_",
            },
            "html": {
                "extract_title": True,
                "strip_dangerous_elements": True,
            },
            "ipynb": {
                "truncate_long_outputs": 50,
            },
            "pdf": {
                "detect_columns": True,
            },
        },
    },
}


def get_preset_names() -> list[str]:
    """Get list of available preset names.

    Returns
    -------
    list[str]
        List of preset names

    Examples
    --------
    >>> names = get_preset_names()
    >>> print(names)
    ['fast', 'quality', 'minimal', 'complete', 'archival', 'documentation']

    """
    return list(PRESETS.keys())


def get_preset_config(preset_name: str) -> Dict[str, Any]:
    """Get configuration dictionary for a preset.

    Parameters
    ----------
    preset_name : str
        Name of the preset

    Returns
    -------
    dict
        Configuration dictionary for the preset

    Raises
    ------
    ValueError
        If preset name is not recognized

    Examples
    --------
    >>> config = get_preset_config("fast")
    >>> print(config['attachment_mode'])
    skip

    """
    if preset_name not in PRESETS:
        available = ", ".join(get_preset_names())
        raise ValueError(f"Unknown preset: {preset_name}. Available presets: {available}")

    return PRESETS[preset_name]["config"].copy()


def get_preset_description(preset_name: str) -> str:
    """Get description for a preset.

    Parameters
    ----------
    preset_name : str
        Name of the preset

    Returns
    -------
    str
        Description of the preset

    Raises
    ------
    ValueError
        If preset name is not recognized

    Examples
    --------
    >>> desc = get_preset_description("fast")
    >>> print(desc)
    Fast processing optimized for speed over quality

    """
    if preset_name not in PRESETS:
        available = ", ".join(get_preset_names())
        raise ValueError(f"Unknown preset: {preset_name}. Available presets: {available}")

    return PRESETS[preset_name]["description"]


def apply_preset(preset_name: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a preset to a base configuration.

    Merges preset configuration into base config, with base config taking
    precedence for any conflicting keys. This allows CLI arguments and
    explicit config files to override preset values.

    Parameters
    ----------
    preset_name : str
        Name of the preset to apply
    base_config : dict
        Base configuration to merge preset into

    Returns
    -------
    dict
        Merged configuration with preset applied

    Raises
    ------
    ValueError
        If preset name is not recognized

    Examples
    --------
    >>> base = {'attachment_mode': 'save'}
    >>> result = apply_preset('fast', base)
    >>> # attachment_mode remains 'save' (base takes precedence)
    >>> print(result['attachment_mode'])
    save
    >>> # But pdf.skip_image_extraction comes from preset
    >>> print(result['pdf']['skip_image_extraction'])
    True

    """
    preset_config = get_preset_config(preset_name)

    # Merge with preset as base and explicit config as override
    # This ensures CLI args and explicit config take precedence
    return merge_configs(preset_config, base_config)


def list_presets() -> list[tuple[str, str]]:
    """Get list of all presets with descriptions.

    Returns
    -------
    list[tuple[str, str]]
        List of (name, description) tuples for all presets

    Examples
    --------
    >>> presets = list_presets()
    >>> for name, desc in presets:
    ...     print(f"{name}: {desc}")
    fast: Fast processing optimized for speed over quality
    quality: High quality processing with maximum fidelity
    ...

    """
    return [(name, data["description"]) for name, data in PRESETS.items()]

#!/usr/bin/env python3
"""Script to update DocumentFormat Literal in constants.py from registry.

This script queries the converter registry to get all registered formats
and updates the DocumentFormat Literal type in constants.py accordingly.

Usage:
    python scripts/update_document_formats.py --validate  # Check if in sync
    python scripts/update_document_formats.py --update    # Update constants.py
    python scripts/update_document_formats.py --dry-run   # Show what would change
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

constants_path = Path(__file__).parent.parent / "src" / "all2md" / "constants.py"


def get_registered_formats() -> list[str]:
    """Get all registered formats from the converter registry.

    Returns
    -------
    list[str]
        Sorted list of format names

    """
    # Add project root to path so we can import all2md
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root / "src"))

    from all2md.converter_registry import registry

    # Auto-discover all converters
    registry.auto_discover()

    # Get all registered formats
    formats = sorted(registry.list_formats())
    return formats


def generate_literal_code(formats: list[str]) -> str:
    """Generate the DocumentFormat Literal code.

    Parameters
    ----------
    formats : list[str]
        List of format names

    Returns
    -------
    str
        Python code for the Literal definition

    """
    # Add "auto" as the first entry
    all_formats = ["auto"] + formats

    # Format as Literal with proper indentation
    lines = ["DocumentFormat = Literal["]

    for fmt in all_formats:
        lines.append(f'    "{fmt}",')

    lines.append("]")

    return "\n".join(lines)


def read_constants_file() -> str:
    """Read the current contents of constants.py.

    Returns
    -------
    str
        File contents

    """
    return constants_path.read_text(encoding="utf-8")


def write_constants_file(content: str) -> None:
    """Write updated content to constants.py.

    Parameters
    ----------
    content : str
        New file contents

    """
    constants_path = Path(__file__).parent.parent / "src" / "all2md" / "constants.py"
    constants_path.write_text(content, encoding="utf-8")


def update_constants_file(new_literal: str) -> tuple[str, bool]:
    """Update the DocumentFormat Literal in constants.py.

    Parameters
    ----------
    new_literal : str
        New Literal code to insert

    Returns
    -------
    tuple[str, bool]
        Updated file content and whether changes were made

    """
    content = read_constants_file()

    # Pattern to match the DocumentFormat Literal definition
    # Matches from "DocumentFormat = Literal[" to the closing "]"
    # Handles entries with or without inline comments
    pattern = r"(# .*\n)*DocumentFormat = Literal\[\s*\n(?:    \"[^\"]+\",.*\n)*\]"

    # Check if pattern exists
    if not re.search(pattern, content):
        raise ValueError("Could not find DocumentFormat Literal definition in constants.py")

    # Replace with new literal (preserve comment if it exists)
    # First, check if there's a comment above
    comment_pattern = r"((?:# .*\n)+)DocumentFormat = Literal\["
    comment_match = re.search(comment_pattern, content)

    if comment_match:
        # Preserve existing comment
        comment = comment_match.group(1)
        new_definition = comment + new_literal
    else:
        # Add new comment
        new_definition = (
            "# Auto-generated from converter registry.\n"
            "# To update: python scripts/update_document_formats.py --update\n" + new_literal
        )

    # Replace the old definition
    new_content = re.sub(pattern, new_definition, content)

    # Check if content changed
    changed = new_content != content

    return new_content, changed


def validate_formats() -> bool:
    """Validate that DocumentFormat Literal matches registry.

    Returns
    -------
    bool
        True if in sync, False if drift detected

    """
    from typing import get_args

    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root / "src"))

    from all2md.constants import DocumentFormat

    # Get formats from Literal
    literal_formats = set(get_args(DocumentFormat))

    # Get formats from registry
    registry_formats = set(get_registered_formats())

    # "auto" should be in Literal but not in registry
    literal_formats_no_auto = literal_formats - {"auto"}

    # Check for differences
    missing_in_literal = registry_formats - literal_formats_no_auto
    extra_in_literal = literal_formats_no_auto - registry_formats

    if missing_in_literal or extra_in_literal:
        print("ERROR: DocumentFormat Literal is out of sync with registry!")
        print()

        if missing_in_literal:
            print(f"Missing in Literal (present in registry): {sorted(missing_in_literal)}")

        if extra_in_literal:
            print(f"Extra in Literal (not in registry): {sorted(extra_in_literal)}")

        print()
        print("Run: python scripts/update_document_formats.py --update")
        return False

    print("SUCCESS: DocumentFormat Literal is in sync with registry")
    return True


def main() -> int:
    """Execute the main entry point.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure)

    """
    parser = argparse.ArgumentParser(description="Update DocumentFormat Literal in constants.py from registry")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--validate", action="store_true", help="Validate that Literal matches registry (exit 1 if drift detected)"
    )
    group.add_argument("--update", action="store_true", help="Update constants.py with current registry formats")
    group.add_argument("--dry-run", action="store_true", help="Show what would change without modifying files")
    group.add_argument("--stage", action="store_true", help="Stage the changes in git")

    args = parser.parse_args()

    if args.validate:
        success = validate_formats()
        return 0 if success else 1

    # Get registered formats
    print("Discovering registered formats...")
    formats = get_registered_formats()
    print(f"Found {len(formats)} registered formats: {', '.join(formats)}")
    print()

    # Generate new Literal code
    new_literal = generate_literal_code(formats)

    if args.dry_run:
        print("Generated Literal code:")
        print(new_literal)
        print()

        # Check if it would change
        try:
            new_content, changed = update_constants_file(new_literal)
            if changed:
                print("STATUS: Changes would be made to constants.py")
            else:
                print("STATUS: No changes needed")
        except Exception as e:
            print(f"ERROR: {e}")
            return 1

        return 0

    if args.update:
        try:
            new_content, changed = update_constants_file(new_literal)

            if changed:
                write_constants_file(new_content)
                print("SUCCESS: Updated constants.py with new DocumentFormat Literal")
                print()
                print("Updated formats:")
                for fmt in formats:
                    print(f"  - {fmt}")

                if args.stage:
                    subprocess.run(["git", "add", str(constants_path)], check=True)
            else:
                print("No changes needed - constants.py is already up to date")

            return 0
        except Exception as e:
            print(f"ERROR: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

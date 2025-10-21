"""Post-process sphinx-apidoc output to fix .rst.rst filename conflicts.

This script renames generated .rst.rst files (from modules named rst.py) to
.restructuredtext.rst to avoid conflicts with the reStructuredText file extension.

It also updates toctree references in parent package files to point to the
renamed files.
"""

import re
from pathlib import Path


def fix_rst_filenames(api_dir: Path) -> None:
    """Fix .rst.rst filename conflicts in sphinx-apidoc output.

    Parameters
    ----------
    api_dir : Path
        Path to the API documentation directory (e.g., docs/source/api)

    """
    # Find all problematic .rst.rst files
    rst_rst_files = list(api_dir.glob("*.rst.rst"))

    if not rst_rst_files:
        print("No .rst.rst files found - nothing to fix")
        return

    print(f"Found {len(rst_rst_files)} .rst.rst files to rename:")

    # Track renames for updating toctree references
    renames = {}

    for rst_file in rst_rst_files:
        # Calculate new filename: all2md.options.rst.rst -> all2md.options.restructuredtext.rst
        old_name = rst_file.name
        new_name = old_name.replace(".rst.rst", ".restructuredtext.rst")
        new_path = rst_file.parent / new_name

        print(f"  {old_name} -> {new_name}")

        if new_path.exists():
            new_path.unlink()
        # Rename the file
        rst_file.rename(new_path)

        # Track the rename (without .rst extension for toctree entries)
        old_ref = old_name[:-4]  # Remove .rst
        new_ref = new_name[:-4]  # Remove .rst
        renames[old_ref] = new_ref

    # Update toctree references in all .rst files in the API directory
    print("\nUpdating toctree references in parent files:")
    updated_count = 0

    for rst_file in api_dir.glob("*.rst"):
        # Skip the renamed files themselves
        if rst_file.name.endswith(".restructuredtext.rst"):
            continue

        content = rst_file.read_text(encoding="utf-8")
        original_content = content

        # Update each toctree reference
        for old_ref, new_ref in renames.items():
            # Match toctree entries (with proper indentation)
            pattern = rf"^(   {re.escape(old_ref)})$"
            replacement = rf"   {new_ref}"
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        # Write back if changed
        if content != original_content:
            rst_file.write_text(content, encoding="utf-8")
            print(f"  Updated {rst_file.name}")
            updated_count += 1

    if updated_count == 0:
        print("  No files needed updating")

    print("\nFilename fix complete!")


if __name__ == "__main__":
    # Determine API directory relative to this script
    script_dir = Path(__file__).parent
    api_dir = script_dir / "source" / "api"

    if not api_dir.exists():
        print(f"Error: API directory not found at {api_dir}")
        exit(1)

    fix_rst_filenames(api_dir)

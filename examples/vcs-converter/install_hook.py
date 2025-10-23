"""Install pre-commit hook for VCS document conversion.

This script installs the pre-commit hook that automatically converts
binary documents to markdown before each commit.
"""

import shutil
import stat
import sys
from pathlib import Path


def find_git_root() -> Path | None:
    """Find the git repository root.

    Returns
    -------
    Path | None
        Path to git root or None if not in a git repository
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def install_hook() -> int:
    """Install the pre-commit hook.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure)
    """
    # Find git root
    git_root = find_git_root()
    if git_root is None:
        print("Error: Not in a git repository")
        return 1

    hooks_dir = git_root / ".git" / "hooks"
    if not hooks_dir.exists():
        print(f"Error: Git hooks directory not found: {hooks_dir}")
        return 1

    # Source and destination paths
    script_dir = Path(__file__).parent
    source_hook = script_dir / "pre-commit-hook.sh"
    dest_hook = hooks_dir / "pre-commit"

    if not source_hook.exists():
        print(f"Error: Hook script not found: {source_hook}")
        return 1

    # Check if hook already exists
    if dest_hook.exists():
        response = input(f"{dest_hook} already exists. Overwrite? [y/N] ")
        if response.lower() != "y":
            print("Installation cancelled")
            return 0

        # Backup existing hook
        backup = dest_hook.with_suffix(".backup")
        shutil.copy2(dest_hook, backup)
        print(f"Backed up existing hook to {backup}")

    # Copy hook
    shutil.copy2(source_hook, dest_hook)

    # Make executable
    dest_hook.chmod(dest_hook.stat().st_mode | stat.S_IEXEC)

    print(f"Successfully installed pre-commit hook to {dest_hook}")
    print("\nThe hook will now automatically convert binary documents to markdown")
    print("before each commit.")
    print("\nTo disable the hook temporarily, use:")
    print("  git commit --no-verify")
    print("\nTo uninstall, simply delete:")
    print(f"  rm {dest_hook}")

    return 0


if __name__ == "__main__":
    sys.exit(install_hook())

#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""Transform listing command for all2md CLI.

This module provides the list-transforms command for displaying information
about available AST transforms, including their descriptions, parameters,
dependencies, and tags. Supports both plain text and rich terminal output.
"""
import argparse
import sys

from all2md.transforms import transform_registry as transform_registry


def _create_list_transforms_parser() -> argparse.ArgumentParser:
    """Create argparse parser for list-transforms command.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for list-transforms command

    """
    parser = argparse.ArgumentParser(
        prog="all2md list-transforms", description="Show available AST transforms.", add_help=True
    )
    parser.add_argument("transform", nargs="?", help="Show details for specific transform")
    parser.add_argument("--rich", action="store_true", help="Use rich terminal output")
    return parser


def handle_list_transforms_command(args: list[str] | None = None) -> int:
    """Handle list-transforms command.

    Parameters
    ----------
    args : list[str], optional
        Additional arguments

    Returns
    -------
    int
        Exit code (0 for success)

    """
    # Parse command line arguments using dedicated parser
    parser = _create_list_transforms_parser()
    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        # argparse calls sys.exit() on --help or error
        # Return the exit code
        return e.code if isinstance(e.code, int) else 0

    # Extract parsed arguments
    specific_transform = parsed.transform
    use_rich = parsed.rich

    # List transforms (auto-discovers on first access)
    transforms = transform_registry.list_transforms()

    if specific_transform:
        if specific_transform not in transforms:
            print(f"Error: Transform '{specific_transform}' not found", file=sys.stderr)
            print(f"Available: {', '.join(transforms)}", file=sys.stderr)
            return 1
        transforms = [specific_transform]

    # Display transforms
    if use_rich:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()

            if specific_transform:
                # Detailed view
                metadata = transform_registry.get_metadata(specific_transform)

                content = []
                content.append(f"[bold]Name:[/bold] {metadata.name}")
                content.append(f"[bold]Description:[/bold] {metadata.description}")
                content.append(f"[bold]Priority:[/bold] {metadata.priority}")
                if metadata.dependencies:
                    content.append(f"[bold]Dependencies:[/bold] {', '.join(metadata.dependencies)}")
                if metadata.tags:
                    content.append(f"[bold]Tags:[/bold] {', '.join(metadata.tags)}")

                console.print(Panel("\n".join(content), title=f"Transform: {metadata.name}"))

                # Parameters table
                if metadata.parameters:
                    table = Table(title="Parameters")
                    table.add_column("Name", style="cyan")
                    table.add_column("Type", style="yellow")
                    table.add_column("Default", style="green")
                    table.add_column("CLI Flag", style="magenta")
                    table.add_column("Description", style="white")

                    for name, spec in metadata.parameters.items():
                        type_str = spec.type.__name__ if hasattr(spec.type, "__name__") else str(spec.type)
                        flag: str = spec.get_cli_flag(name) if spec.should_expose() else "N/A"
                        table.add_row(
                            name,
                            type_str,
                            str(spec.default) if spec.default is not None else "None",
                            flag,
                            spec.help or "",
                        )

                    console.print(table)
            else:
                # Summary table
                table = Table(title=f"Available Transforms ({len(transforms)})")
                table.add_column("Name", style="cyan")
                table.add_column("Description", style="white")
                table.add_column("Tags", style="yellow")

                for name in transforms:
                    metadata = transform_registry.get_metadata(name)
                    table.add_row(
                        metadata.name, metadata.description, ", ".join(metadata.tags) if metadata.tags else ""
                    )

                console.print(table)
        except ImportError:
            use_rich = False

    if not use_rich:
        # Plain text output
        if specific_transform:
            metadata = transform_registry.get_metadata(specific_transform)
            print(f"\n{metadata.name}")
            print("=" * 60)
            print(f"Description: {metadata.description}")
            print(f"Priority: {metadata.priority}")
            if metadata.dependencies:
                print(f"Dependencies: {', '.join(metadata.dependencies)}")
            if metadata.tags:
                print(f"Tags: {', '.join(metadata.tags)}")

            if metadata.parameters:
                print("\nParameters:")
                for name, spec in metadata.parameters.items():
                    type_str = spec.type.__name__ if hasattr(spec.type, "__name__") else str(spec.type)
                    default_str = f"(default: {spec.default})" if spec.default is not None else ""
                    cli_flag: str | None = spec.get_cli_flag(name) if spec.should_expose() else None
                    print(f"  {name} ({type_str}) {default_str}")
                    if spec.help:
                        print(f"    {spec.help}")
                    if cli_flag:
                        print(f"  CLI: {cli_flag}")
        else:
            print("\nAvailable Transforms")
            print("=" * 60)
            for name in transforms:
                metadata = transform_registry.get_metadata(name)
                tags_str = f" [{', '.join(metadata.tags)}]" if metadata.tags else ""
                print(f"  {metadata.name:20} {metadata.description}{tags_str}")
            print(f"\nTotal: {len(transforms)} transforms")
            print("Use 'all2md list-transforms <transform>' for details")

    return 0

"""Handler for the interactive ``all2md batch`` subcommand.

This command walks the user through the common batch-conversion workflow — choosing
and previewing input files, output location and structure, attachment handling,
file-type-specific options, and advanced parameters — then prints the equivalent
``all2md ...`` command and offers to run it.

The wizard prefers the optional Rich UI (``all2md[cli_extras]``) for prompts and tables
but degrades gracefully to plain ``input()`` when Rich is unavailable.
"""

from __future__ import annotations

import dataclasses
import logging
import shlex
from collections import Counter
from typing import Optional, Sequence

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS
from all2md.cli.commands.shared import collect_input_files
from all2md.cli.input_items import CLIInputItem
from all2md.converter_registry import registry

logger = logging.getLogger(__name__)

ATTACHMENT_MODES = ["skip", "alt_text", "save", "base64"]


# ---------------------------------------------------------------------------
# Prompt helpers (Rich when available, plain input() otherwise)
# ---------------------------------------------------------------------------


class _Prompter:
    """Thin prompt layer that uses Rich when installed and falls back to input()."""

    def __init__(self) -> None:
        self.console = None
        self._rich = None
        try:
            from rich.console import Console
            from rich.prompt import Confirm, IntPrompt, Prompt

            self.console = Console()
            self._rich = (Prompt, IntPrompt, Confirm)
        except Exception:  # pragma: no cover - exercised only without rich installed
            self.console = None
            self._rich = None

    @property
    def has_rich(self) -> bool:
        return self._rich is not None

    def print(self, message: str = "") -> None:
        if self.console is not None:
            self.console.print(message)
        else:
            print(_strip_markup(message))

    def rule(self, title: str) -> None:
        if self.console is not None:
            self.console.rule(title)
        else:
            print(f"\n== {title} ==")

    def ask(self, prompt: str, default: Optional[str] = None) -> str:
        if self._rich is not None:
            Prompt = self._rich[0]
            if default is None:
                return str(Prompt.ask(prompt, console=self.console))
            return str(Prompt.ask(prompt, default=default, console=self.console))
        return _plain_ask(prompt, default)

    def ask_choice(self, prompt: str, choices: Sequence[str], default: str) -> str:
        if self._rich is not None:
            Prompt = self._rich[0]
            return Prompt.ask(prompt, choices=list(choices), default=default, console=self.console)
        while True:
            value = _plain_ask(f"{prompt} {list(choices)}", default)
            if value in choices:
                return value
            print(f"  Please choose one of: {', '.join(choices)}")

    def ask_int(self, prompt: str, default: Optional[int]) -> Optional[int]:
        if self._rich is not None:
            IntPrompt = self._rich[1]
            return IntPrompt.ask(prompt, default=default, console=self.console)
        raw = _plain_ask(prompt, None if default is None else str(default))
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def confirm(self, prompt: str, default: bool = False) -> bool:
        if self._rich is not None:
            Confirm = self._rich[2]
            return bool(Confirm.ask(prompt, default=default, console=self.console))
        suffix = "Y/n" if default else "y/N"
        raw = _plain_ask(f"{prompt} [{suffix}]", None)
        if not raw:
            return default
        return raw.strip().lower() in {"y", "yes"}


def _plain_ask(prompt: str, default: Optional[str]) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"{_strip_markup(prompt)}{suffix}: ").strip()
    except EOFError:
        raw = ""
    return raw if raw else (default or "")


def _strip_markup(text: str) -> str:
    """Best-effort removal of Rich markup tags for the plain-text fallback."""
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch == "[":
            depth += 1
            continue
        if ch == "]" and depth:
            depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _step_inputs(p: _Prompter) -> Optional[tuple[list[str], list[CLIInputItem], dict]]:
    """Collect input pattern + filters and preview detected file types.

    Returns ``(input_args, items, flags)`` where ``flags`` records recursive/exclude/
    include_hidden choices, or ``None`` if the user aborts with no usable inputs.
    """
    p.rule("1. Choose files")
    pattern = p.ask("Input directory, file, or glob (e.g. [cyan]'**/*.pdf'[/cyan])", default=".")
    recursive = p.confirm("Recurse into subdirectories?", default=True)
    include_hidden = p.confirm("Include hidden dot-files/folders?", default=False)

    excludes: list[str] = []
    while p.confirm("Add an exclude glob pattern?", default=False):
        pat = p.ask("Exclude pattern (e.g. [cyan]*.tmp[/cyan])")
        if pat:
            excludes.append(pat)

    items = collect_input_files(
        [pattern],
        recursive=recursive,
        exclude_patterns=excludes or None,
        include_hidden=include_hidden,
    )
    if not items:
        p.print("[yellow]No matching files found.[/yellow]")
        return None

    counts = _counts_by_suffix(items)
    _print_type_table(p, counts, len(items))

    # Optional narrowing by extension.
    chosen_exts: Optional[list[str]] = None
    if len(counts) > 1 and p.confirm("Restrict to specific file types?", default=False):
        available = sorted(counts)
        wanted = p.ask(
            "Comma-separated extensions to keep (e.g. [cyan].pdf,.docx[/cyan])",
            default=",".join(available),
        )
        chosen_exts = [_normalize_ext(e) for e in wanted.split(",") if e.strip()]
        items = [it for it in items if (it.suffix.lower() in chosen_exts)]
        if not items:
            p.print("[yellow]No files left after filtering.[/yellow]")
            return None
        _print_type_table(p, _counts_by_suffix(items), len(items))

    flags = {
        "recursive": recursive,
        "include_hidden": include_hidden,
        "excludes": excludes,
    }
    return [pattern], items, flags


def _step_output(p: _Prompter) -> dict:
    """Collect output directory, structure preservation, format, and extension."""
    p.rule("2. Output location & structure")
    output_dir = p.ask("Output directory", default="converted")
    preserve = p.confirm(
        "Preserve the input directory structure in the output?",
        default=True,
    )
    if preserve:
        p.print(
            "  [dim]Outputs mirror the input tree; with save mode, attachments land in a "
            "shared .attachments folder beside each file.[/dim]"
        )
    output_format = p.ask("Output format", default="markdown")
    extension = p.ask("Custom output extension (blank for default)", default="")
    return {
        "output_dir": output_dir,
        "preserve": preserve,
        "output_format": output_format,
        "extension": extension.strip(),
    }


def _step_attachments(p: _Prompter, preserve: bool) -> dict:
    """Collect attachment mode and (optionally) an explicit output directory."""
    p.rule("3. Attachment handling")
    mode = p.ask_choice("How should images / embedded files be handled?", ATTACHMENT_MODES, default="save")
    attachment_dir = ""
    if mode == "save":
        if preserve:
            p.print(
                "  [dim]With --preserve-structure, attachments default to a .attachments folder "
                "beside each output file.[/dim]"
            )
            if p.confirm("Override that with a single shared attachments directory?", default=False):
                attachment_dir = p.ask("Attachment output directory", default="attachments")
        else:
            attachment_dir = p.ask(
                "Attachment output directory (blank for default 'attachments')",
                default="",
            ).strip()
    return {"mode": mode, "attachment_dir": attachment_dir}


def _step_format_options(p: _Prompter, items: list[CLIInputItem]) -> list[str]:
    """Surface file-type-specific options for the formats present and collect extra flags."""
    p.rule("4. File-type options")
    formats = _detect_formats(items)
    if not formats:
        p.print("  [dim]No format-specific options detected.[/dim]")
        return []

    extra: list[str] = []
    for fmt in formats:
        hints = _core_option_flags(fmt)
        if hints:
            p.print(f"[bold]{fmt}[/bold] options (see [cyan]all2md help {fmt}[/cyan] for all):")
            for flag, help_text in hints:
                p.print(f"  [green]{flag}[/green] — {help_text}")
        else:
            p.print(f"[bold]{fmt}[/bold]: see [cyan]all2md help {fmt}[/cyan] for options.")
        raw = p.ask(f"Extra flags for {fmt} files (blank to skip)", default="")
        if raw.strip():
            try:
                extra.extend(shlex.split(raw))
            except ValueError:
                p.print("  [yellow]Could not parse those flags; skipping.[/yellow]")
    return extra


def _step_advanced(p: _Prompter) -> dict:
    """Collect worker count and error-handling preference."""
    p.rule("5. Advanced parameters")
    use_parallel = p.confirm("Convert files in parallel?", default=True)
    workers: Optional[int] = None
    if use_parallel:
        workers = p.ask_int("Worker count (blank/0 = auto-detect)", default=0)
        if workers is not None and workers <= 0:
            workers = None  # auto
    skip_errors = p.confirm("Continue past files that fail to convert?", default=True)
    return {"parallel": use_parallel, "workers": workers, "skip_errors": skip_errors}


# ---------------------------------------------------------------------------
# Detection / option helpers
# ---------------------------------------------------------------------------


def _counts_by_suffix(items: list[CLIInputItem]) -> Counter:
    counter: Counter = Counter()
    for item in items:
        suffix = item.suffix.lower() or "(no extension)"
        counter[suffix] += 1
    return counter


def _normalize_ext(ext: str) -> str:
    ext = ext.strip().lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return ext


def _print_type_table(p: _Prompter, counts: Counter, total: int) -> None:
    if p.console is not None:
        try:
            from rich.table import Table

            table = Table(title=f"{total} file(s) detected")
            table.add_column("Type", style="cyan")
            table.add_column("Count", justify="right", style="green")
            for suffix, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                table.add_row(suffix, str(count))
            p.console.print(table)
            return
        except Exception:  # pragma: no cover - defensive
            pass
    p.print(f"{total} file(s) detected:")
    for suffix, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        p.print(f"  {suffix}: {count}")


def _detect_formats(items: list[CLIInputItem]) -> list[str]:
    """Return the distinct parser formats present, one detection per suffix group."""
    formats: list[str] = []
    seen_suffix: set[str] = set()
    for item in items:
        suffix = item.suffix.lower()
        if suffix in seen_suffix:
            continue
        seen_suffix.add(suffix)
        path = item.best_path()
        if path is None:
            continue
        try:
            fmt = registry.detect_format(path)
        except Exception:
            fmt = None
        if fmt and fmt not in formats:
            formats.append(fmt)
    return formats


def _core_option_flags(fmt: str) -> list[tuple[str, str]]:
    """Return ``(flag, help)`` pairs for the ``core`` options of *fmt* (best effort).

    Attachment-mode options are excluded because they are handled in the dedicated
    attachment step. Returns an empty list if the format's options can't be introspected.
    """
    try:
        options_cls = registry.get_parser_options_class(fmt)
    except Exception:
        options_cls = None
    if options_cls is None or not dataclasses.is_dataclass(options_cls):
        return []

    skip = {"attachment_mode", "alt_text_mode"}
    flags: list[tuple[str, str]] = []
    for field in dataclasses.fields(options_cls):
        if field.name in skip:
            continue
        meta = field.metadata
        if meta.get("importance") != "core":
            continue
        flag = f"--{fmt}-{field.name.replace('_', '-')}"
        help_text = str(meta.get("help", "")).strip()
        flags.append((flag, help_text))
    return flags


# ---------------------------------------------------------------------------
# Command assembly + execution
# ---------------------------------------------------------------------------


def _build_argv(
    input_args: list[str],
    in_flags: dict,
    out: dict,
    attach: dict,
    fmt_extra: list[str],
    advanced: dict,
) -> list[str]:
    """Assemble the equivalent ``all2md`` argv from the collected wizard choices."""
    argv: list[str] = list(input_args)

    if in_flags["recursive"]:
        argv.append("--recursive")
    if in_flags["include_hidden"]:
        argv.append("--include-hidden")
    for pat in in_flags["excludes"]:
        argv += ["--exclude", pat]

    argv += ["--output-dir", out["output_dir"]]
    if out["preserve"]:
        argv.append("--preserve-structure")
    if out["output_format"] and out["output_format"] != "markdown":
        argv += ["--output-format", out["output_format"]]
    if out["extension"]:
        argv += ["--output-extension", out["extension"]]

    argv += ["--attachment-mode", attach["mode"]]
    if attach["attachment_dir"]:
        argv += ["--attachment-output-dir", attach["attachment_dir"]]

    argv += fmt_extra

    if advanced["parallel"]:
        if advanced["workers"]:
            argv += ["--parallel", str(advanced["workers"])]
        else:
            argv.append("--parallel")
    if advanced["skip_errors"]:
        argv.append("--skip-errors")

    return argv


def _render_command(argv: list[str]) -> str:
    return "all2md " + " ".join(shlex.quote(a) for a in argv)


def handle_batch_command(args: list[str] | None = None) -> int:
    """Entry point for ``all2md batch`` — the interactive batch wizard.

    Parameters
    ----------
    args : list[str], optional
        Arguments past ``batch`` (currently unused; reserved for future presets).

    Returns
    -------
    int
        Process exit code. Mirrors the exit code of the underlying conversion when the
        user chooses to run it; ``EXIT_SUCCESS`` if they decline.

    """
    p = _Prompter()
    p.print("[bold]all2md batch[/bold] — interactive batch conversion")
    if not p.has_rich:
        p.print("(Install [cyan]all2md[cli_extras][/cyan] for a richer experience.)")

    try:
        collected = _step_inputs(p)
        if collected is None:
            return EXIT_SUCCESS
        input_args, items, in_flags = collected

        out = _step_output(p)
        attach = _step_attachments(p, out["preserve"])
        fmt_extra = _step_format_options(p, items)
        advanced = _step_advanced(p)
    except (KeyboardInterrupt, EOFError):
        p.print("\n[yellow]Cancelled.[/yellow]")
        return EXIT_SUCCESS

    argv = _build_argv(input_args, in_flags, out, attach, fmt_extra, advanced)

    p.rule("Review")
    p.print("Equivalent command:\n")
    p.print(f"  [green]{_render_command(argv)}[/green]\n")
    p.print(f"This will convert [bold]{len(items)}[/bold] file(s).")

    if not p.confirm("Run it now?", default=True):
        p.print("Not running. You can copy the command above to run it later.")
        return EXIT_SUCCESS

    # Execute by reusing the full CLI pipeline so all parsing/validation is shared.
    from all2md.cli import main as cli_main

    try:
        return cli_main(argv)
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        logger.error("Batch conversion failed: %s", exc)
        p.print(f"[red]Conversion failed: {exc}[/red]")
        return EXIT_ERROR

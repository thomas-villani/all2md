"""Document lifecycle over COM, as a CLI. ``wordlive`` has no create/close verb.

Generation side: **Windows + Word only**, hand-run.

    uv run --with pywin32 python worddoc.py new             -> prints the new name
    uv run --with pywin32 python worddoc.py list
    uv run --with pywin32 python worddoc.py close NAME      -> discard changes
    uv run --with pywin32 python worddoc.py closeall-but NAME
    uv run --with pywin32 python worddoc.py activate NAME
    uv run --with pywin32 python worddoc.py alerts off|on

:mod:`session` does all of this in-process; this exists for the interactive case,
where a generation run has died half way and Word is left holding documents.
``alerts off`` is worth knowing by hand: with alerts on, one modal hangs every
later ``wordlive`` call forever.
"""

from __future__ import annotations

import sys
from typing import Any

import win32com.client as win32

WD_DO_NOT_SAVE = 0
WD_ALERTS_NONE = 0
WD_ALERTS_ALL = -1


def app() -> Any:
    return win32.GetActiveObject("Word.Application")


def main() -> int:
    word = app()
    command = sys.argv[1]
    if command == "new":
        document = word.Documents.Add()
        document.Activate()
        print(document.Name)
    elif command == "list":
        for document in word.Documents:
            print(f"{document.Name}\t{document.FullName}\tsaved={document.Saved}")
    elif command == "close":
        word.Documents(sys.argv[2]).Close(WD_DO_NOT_SAVE)
        print(f"closed {sys.argv[2]}")
    elif command == "closeall-but":
        keep = sys.argv[2]
        for document in list(word.Documents):
            if document.Name != keep:
                document.Close(WD_DO_NOT_SAVE)
        print("ok")
    elif command == "activate":
        word.Documents(sys.argv[2]).Activate()
        print("ok")
    elif command == "alerts":
        word.DisplayAlerts = WD_ALERTS_NONE if sys.argv[2] == "off" else WD_ALERTS_ALL
        print(f"alerts {sys.argv[2]}")
    else:
        raise SystemExit(f"unknown command {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

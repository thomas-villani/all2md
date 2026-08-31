"""Driving a live Word over COM + ``wordlive``, with the probe's scars baked in.

Generation side of the lane. **Windows + a Word install only**, hand-run, never
imported by anything CI executes -- see ``generate/README.md`` for why the corpus bytes
are committed instead.

Every rule below cost something to learn during the 2026-08-23 capability probe. They
are enforced here rather than written down, so a case script cannot re-learn them:

* Word's document counter is **global** and advances for documents other programs
  create, so ``DocumentN`` can never be hard-coded -- capture what ``Documents.Add()``
  returns.
* ``save-as`` **renames the open document** to the file name, so every later
  ``--doc`` must use the new name. :meth:`WordSession.save_as` tracks that.
* ``Application.DisplayAlerts = 0`` goes up front. A single modal (a plain-text
  content control on an illegal range will do it) hangs *every* later ``wordlive``
  call indefinitely, which is far worse than a non-zero exit -- there is nothing to
  time out against. ``dismiss-dialogs.ps1`` is the rescue hatch when it happens
  anyway.
* ``WORDLIVE_SAVE_DIRS`` must contain the output directory or ``save-as`` exits 1.
* Word quits if its last document closes, so a session keeps one open.

One more that this class cannot enforce, because it is about the order a *case*
does things in -- the **offset-space rule**: ``find`` offsets count visible text,
while ``range:``/``paragraphs`` offsets are Word Range offsets that also count
hidden field codes, note marks and content-control boundaries. The two diverge as
soon as any of those exist (one hyperlink field measured 39 characters of drift).
So a case script does find-based styling *before* it inserts fields, notes, content
controls or links -- or derives positions from ``paragraphs`` and confirms with
``read text`` before anything destructive.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import win32com.client as win32

#: ``wdDoNotSaveChanges`` -- close discarding, since the file is already written.
WD_DO_NOT_SAVE = 0
#: ``wdAlertsNone``. See the module docstring: this is not optional.
WD_ALERTS_NONE = 0
#: ``wdTrailingTab``.
WD_TRAILING_TAB = 0
#: A generated document should never take this long; a hang means a modal is up.
CALL_TIMEOUT = 180


class WordSession:
    """One live Word application, driven document by document."""

    def __init__(self, outdir: str, user_name: str | None = None) -> None:
        self.outdir = os.path.abspath(outdir)
        os.makedirs(self.outdir, exist_ok=True)
        self.app = win32.GetActiveObject("Word.Application")
        self.app.DisplayAlerts = WD_ALERTS_NONE
        if user_name is not None:
            # Tracked-change authorship is written from Word's identity, so an
            # unpinned name would put whoever generated the corpus into the truth
            # records and make them unreproducible on another machine.
            self.app.UserName = user_name
        self.env = dict(os.environ, WORDLIVE_SAVE_DIRS=self.outdir)
        self.doc_name: str | None = None

    # --- lifecycle ------------------------------------------------------
    def new(self) -> str:
        """Open a blank document. ``wordlive`` has no create verb; this is COM."""
        doc = self.app.Documents.Add()
        doc.Activate()
        self.doc_name = str(doc.Name)
        return self.doc_name

    def save_as(self, filename: str) -> str:
        path = os.path.join(self.outdir, filename)
        self.wl("save-as", path, "--overwrite")
        self.doc_name = filename  # the rename -- see the module docstring
        return path

    def close(self) -> None:
        self.app.Documents(self.doc_name).Close(WD_DO_NOT_SAVE)
        self.doc_name = None

    def doc(self) -> Any:
        """Return the live COM ``Document``, for recipes ``wordlive`` has no verb for."""
        return self.app.Documents(self.doc_name)

    # --- driving wordlive -----------------------------------------------
    def wl(self, *args: str, stdin: str | None = None) -> Any:
        cmd = ["wordlive", "--doc", str(self.doc_name), *args]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self.env,
            input=stdin,
            encoding="utf-8",
            timeout=CALL_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(f"exit {result.returncode}: {' '.join(args)}\n{result.stderr.strip()}")
        return json.loads(result.stdout)

    def exec_ops(self, ops: list[dict[str, Any]], label: str = "batch", tracked: bool = False) -> Any:
        """Run a batch of ops. ``tracked=True`` records them as ``w:ins``/``w:del``."""
        payload = json.dumps({"label": label, "tracked": tracked, "ops": ops})
        return self.wl("exec", "--ops", "-", stdin=payload)

    # --- COM escape hatches ---------------------------------------------
    def link_list_style(
        self,
        style: str,
        number_style: int = 0,
        fmt: str = "%1.",
        start: int = 1,
        indent: float = 18.0,
        template_name: str | None = None,
    ) -> None:
        """Put ``w:numPr`` on a paragraph **style**, the way corporate templates do.

        There is no ``wordlive`` verb for this, and it is the whole point of the
        style-inherited-numbering family: the paragraphs end up carrying only
        ``w:pStyle``, with the numbering reachable only through ``styles.xml``.

        ``number_style`` is a ``WdListNumberStyle`` constant. The COM constant
        *names* are misleading about which OOXML ``w:numFmt`` they produce, so use
        ``numfmt-map.json`` -- it was measured, not read off the documentation.

        Note ``LinkToListTemplate`` clones the template and leaves an orphan
        ``w:abstractNum`` behind. That is harmless, and arguably realistic: real
        corporate templates are full of them.
        """
        document = self.doc()
        template = document.ListTemplates.Add(OutlineNumbered=True)
        level = template.ListLevels(1)
        level.NumberStyle = number_style
        level.NumberFormat = fmt
        level.StartAt = start
        level.TrailingCharacter = WD_TRAILING_TAB
        level.NumberPosition = indent
        level.TextPosition = indent + 18
        level.TabPosition = indent + 18
        if template_name is not None:
            template.Name = template_name  # becomes a w:abstractNum w:name
        document.Styles(style).LinkToListTemplate(ListTemplate=template, ListLevelNumber=1)

    def add_paragraph_style(self, name: str, based_on: str, park_at: str = "para:1") -> None:
        """Create a paragraph style, parking the cursor first.

        ``style add --type paragraph`` seeds the new style's ``rPr`` from **the
        formatting under the cursor**, so creating a style while sitting in a bold
        heading silently produces a bold style. Park on a plain paragraph first.
        It also auto-creates a linked character style, which the truth records for
        the formatting family have to expect.
        """
        self.wl("go-to", "--anchor-id", park_at)
        self.wl("style", "add", name, "--type", "paragraph", "--based-on", based_on)

"""The interactive terminal viewer, ``all2md read``, built on Wijjit.

``Viewer`` turns a ``DocumentLayout`` into a Wijjit app: the document in a
scrolling body, a side panel that shows the outline, the links on screen or
the keys, and a status bar with the file, the current section and the
position. Keys come from ``keys.py``; nothing here hard-codes one. Given a
``FileTree``, the panel also shows the files of a folder, and choosing one
opens it in the body.

Links are never opened by the viewer. A ``#fragment`` link or a footnote
reference moves the viewer (with back and forward); anything else is shown in
the status bar, and can be copied, but not launched. The terminal's own
Ctrl+click works only on the links ``--clickable-links`` makes clickable (none
by default); Wijjit keeps those OSC 8 links.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from all2md.renderers.terminal import LinkPosition
from all2md.tui.files import FileTree
from all2md.tui.keys import Action, help_rows, key_name, keymap
from all2md.tui.layout import DocumentLayout, OutlineEntry

#: Keys a focused tree uses for itself; the viewer leaves them to it.
TREE_KEYS = frozenset({"up", "down", "left", "right", "pageup", "pagedown", "home", "end", "space", "enter"})

#: The side panel's choices.
PANELS = ("outline", "links", "help", "files")

#: Trees with at most this many files open with every folder open.
OPEN_FOLDERS_UP_TO = 300

_TEMPLATE = """
{% vstack width="fill" height="fill" %}
  {% hstack width="fill" height="fill" %}
    {% if panel == "outline" %}
    {% tree id="outline" data=outline_data width=panel_width height="fill" show_root=false bind=false
       expanded=expanded enter_selects=true on_select="outline_select" border="single" title="Outline" %}{% endtree %}
    {% elif panel == "links" %}
    {% tree id="links" data=link_data width=panel_width height="fill" show_root=false bind=false
       enter_selects=true on_select="link_select" border="single" title="Links on screen" %}{% endtree %}
    {% elif panel == "files" %}
    {% tree id="files" data=files_data width=files_width height="fill" show_root=false bind=false
       expanded="files_expanded" on_select="file_select" border="single" title=files_title
       autofocus=true %}{% endtree %}
    {% elif panel == "help" %}
    {% contentview id="help" content=help_text content_type="plain" width=panel_width height="fill"
       bind=false border="single" title="Keys" %}{% endcontentview %}
    {% endif %}
    {% contentview id="body" content=content content_type="ansi" width="fill" height="fill"
       bind=false action="body_click" border="single" title=title %}{% endcontentview %}
  {% endhstack %}
  {% statusbar id="status" left=status_left center=center right=position bind=false %}{% endstatusbar %}
{% endvstack %}
"""


def wijjit_available() -> bool:
    """Return whether Wijjit can be imported (the ``tui`` extra, Python 3.11+)."""
    from importlib.util import find_spec

    return find_spec("wijjit") is not None


class Viewer:
    """A Wijjit app showing one document at a time.

    Parameters
    ----------
    layout : DocumentLayout or None
        The document to show; None to start in the file tree.
    title : str
        Shown in the body's border and the status bar; usually the file name.
    preset : str, default "default"
        Key preset from ``all2md.tui.keys.PRESETS``.
    outline : bool, default True
        Open with the outline panel showing (when the document has headings).
    panel_width : int, default 32
        Width of the side panel in columns.
    files : FileTree, optional
        Documents to choose from in the ``files`` panel.
    opener : callable, optional
        Lays out a file chosen there; what it raises is shown in the status bar.

    """

    def __init__(
        self,
        layout: Optional[DocumentLayout],
        title: str,
        preset: str = "default",
        outline: bool = True,
        panel_width: int = 32,
        files: Optional[FileTree] = None,
        opener: Optional[Callable[[Path], DocumentLayout]] = None,
    ) -> None:
        """Build the app; ``run()`` starts it."""
        from wijjit import Wijjit
        from wijjit.core.events import EventType

        self.files = files
        self.opener = opener
        # The file open from the tree, which the tree marks when it is shown again.
        self.current: Optional[Path] = None
        self.show_outline = outline
        self.layout = layout if layout is not None else _placeholder(files)
        self.title = title
        self.keys = keymap(preset)
        self.preset = preset
        self.panel_width = panel_width
        # The body's width at the last layout, to move the view along on a resize.
        self.width: Optional[int] = None
        # Where links were followed from, and where back went from: (line, width).
        self.history: list[tuple[int, int]] = []
        self.future: list[tuple[int, int]] = []
        # The external link last shown, for copying.
        self.shown_target: Optional[str] = None
        # The same callable on every render, so ContentView lays out only on a new width.
        self.content = self._content

        if layout is None and files is not None:
            panel = "files"
        else:
            panel = "outline" if outline and self.layout.outline else ""
        expanded = ["root"]
        if files is not None and len(files.files) <= OPEN_FOLDERS_UP_TO:
            expanded += files.folder_ids()
        self.app: Wijjit = Wijjit(initial_state={"panel": panel, "message": "", "files_expanded": expanded})
        self.app.view("main", default=True)(self._view)
        self.app.on(EventType.KEY)(self._on_key)
        self.app.on_action("outline_select")(self._on_outline_select)
        self.app.on_action("link_select")(self._on_link_select)
        self.app.on_action("body_click")(self._on_body_click)
        self.app.on_action("file_select")(self._on_file_select)

    def run(self) -> None:
        """Run the viewer until it quits."""
        self.app.run()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _content(self, width: int) -> str:
        """Lay the document out at the body's width, keeping the view in place on a resize."""
        if self.width is not None and width != self.width:
            body = self._body()
            if body is not None:
                moved = self.layout.relocate(body.scroll_position, self.width, width)
                # Set directly: ContentView clamps it to the new length after this call.
                body.scroll_manager.state.scroll_position = moved
            self.history = [(self.layout.relocate(line, old, width), width) for line, old in self.history]
            self.future = [(self.layout.relocate(line, old, width), width) for line, old in self.future]
        self.width = width
        return self.layout.text(width)

    def _view(self) -> Any:
        from wijjit import render_template_string

        state = self.app.state
        panel = state.get("panel", "")
        top, height = self._viewport()
        return render_template_string(
            _TEMPLATE,
            panel=panel,
            panel_width=self.panel_width,
            content=self.content,
            title=self.title,
            status_left=self._status_left(),
            outline_data=_root(_outline_nodes(self.layout.outline)) if panel == "outline" else _root([]),
            expanded=["root"] + [f"h{entry.index}" for entry in self.layout.outline],
            link_data=_root(self._link_nodes(top, height) if panel == "links" else []),
            help_text=self._help_text() if panel == "help" else "",
            files_data=_root(self.files.nodes() if panel == "files" and self.files is not None else []),
            files_width=self.panel_width + 8,
            files_title=self._files_title(),
            center=state.get("message") or self._section(top),
            position=self._position(top, height),
        )

    def _files_title(self) -> str:
        if self.files is None:
            return ""
        more = f" (first {len(self.files.files)})" if self.files.truncated else ""
        return f"{self.files.root.name or self.files.root}{more}"

    def _section(self, top: int) -> str:
        if self.width is None:
            return ""
        index = self.layout.section_at(top, self.width)
        return "" if index is None else self.layout.headings[index].text

    def _position(self, top: int, height: int) -> str:
        if self.width is None:
            return ""
        count = self.layout.at(self.width).line_count
        if count == 0:
            return "empty"
        last = min(top + height, count)
        percent = 100 if last >= count else (100 * last) // count
        return f"{top + 1}-{last}/{count}  {percent}%"

    def _link_nodes(self, top: int, height: int) -> list[dict[str, Any]]:
        if self.width is None:
            return []
        nodes = []
        for position in self.layout.links_between(top, top + height, self.width):
            label = self.layout.link_label(position, self.width) or position.target
            hint = "footnote" if position.footnote else position.target
            nodes.append({"id": f"l{position.index}", "label": f"{label}  -> {hint}", "children": []})
        if not nodes:
            nodes.append({"id": "none", "label": "(no links on screen)", "children": []})
        return nodes

    def _help_text(self) -> str:
        rows = []
        for keys, description in help_rows(self.preset):
            rows += [keys, f"  {description}"]
        return chr(10).join(rows)

    def _status_left(self) -> str:
        """Return the title, with the key that shows the keys while the help panel is closed."""
        help_keys = [key for key, action in self.keys.items() if action is Action.HELP]
        if not help_keys or self.app.state.get("panel") == "help":
            return self.title
        return f"{self.title}  ({key_name(help_keys[0])} keys)"

    # ------------------------------------------------------------------
    # Moving around
    # ------------------------------------------------------------------

    def _body(self) -> Any:
        return self.app.get_element_by_id("body")

    def _viewport(self) -> tuple[int, int]:
        """Return the body's first visible line and its height in lines."""
        body = self._body()
        if body is None:
            return 0, 1
        return body.scroll_position, max(1, body.scroll_manager.state.viewport_size)

    def scroll_to(self, line: int) -> None:
        """Show ``line`` at the top of the body (clamped to the document)."""
        body = self._body()
        if body is not None:
            body.scroll_manager.scroll_to(max(0, line))

    def jump(self, line: int) -> None:
        """Move to ``line``, remembering where from for ``back``."""
        top, _ = self._viewport()
        if self.width is not None:
            self.history.append((top, self.width))
            self.future.clear()
        self.scroll_to(line)

    def follow(self, position: LinkPosition) -> None:
        """Follow a link: move to it if it is in the document, else only show where it goes."""
        if self.width is None:
            return
        line = self.layout.jump_target(position, self.width)
        if line is not None:
            self.jump(line)
            self.app.state["message"] = f"-> {self.layout.link_label(position, self.width)}"
            return
        self.shown_target = position.target
        copy_keys = [key for key, action in self.keys.items() if action is Action.COPY_LINK]
        hint = f"  ({key_name(copy_keys[0])} copies it)" if copy_keys else ""
        self.app.state["message"] = f"Not opened: {position.target}{hint}"

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_key(self, event: Any) -> None:
        action = self.keys.get(event.key)
        if action is None:
            return
        focused = self.app.focus_manager.get_focused_element()
        if getattr(focused, "id", None) in ("outline", "links", "files") and event.key in TREE_KEYS:
            return
        event.cancel()
        self.app.state["message"] = ""
        self.perform(action)

    def perform(self, action: Action) -> None:  # noqa: C901
        """Do what a key bound to ``action`` does."""
        top, height = self._viewport()
        body = self._body()
        if action is Action.QUIT:
            self.app.quit()
        elif action in _SCROLLS and body is not None:
            body.scroll_manager.scroll_by(_SCROLLS[action](height))
        elif action is Action.TOP:
            self.scroll_to(0)
        elif action is Action.BOTTOM and body is not None:
            body.scroll_manager.scroll_to_bottom()
        elif action in (Action.NEXT_HEADING, Action.PREVIOUS_HEADING) and self.width is not None:
            find = self.layout.next_heading if action is Action.NEXT_HEADING else self.layout.previous_heading
            line = find(top, self.width)
            if line is not None:
                self.scroll_to(line)
        elif action in (Action.TOGGLE_OUTLINE, Action.LINKS, Action.HELP):
            panel = {Action.TOGGLE_OUTLINE: "outline", Action.LINKS: "links", Action.HELP: "help"}[action]
            self.app.state["panel"] = "" if self.app.state.get("panel") == panel else panel
        elif action is Action.FILES:
            self._toggle_files()
        elif action is Action.BACK and self.history and self.width is not None:
            self.future.append((top, self.width))
            line, _ = self.history.pop()
            self.scroll_to(line)
        elif action is Action.FORWARD and self.future and self.width is not None:
            self.history.append((top, self.width))
            line, _ = self.future.pop()
            self.scroll_to(line)
        elif action is Action.COPY_LINK:
            self._copy()
        self.app.refresh()

    def open(self, path: Path) -> None:
        """Open a file from the tree in the body, in place of the document shown."""
        if self.opener is None:
            return
        try:
            layout = self.opener(path)
        except Exception as error:  # any parser's error; the viewer stays on the current document
            self.app.state["message"] = f"Could not read {path.name}: {error}"
            return
        self.layout = layout
        self.title = path.name
        self.current = path
        self.width = None
        self.history.clear()
        self.future.clear()
        self.shown_target = None
        # A new callable, so ContentView lays the new document out.
        self.content = self._content
        body = self._body()
        if body is not None:
            body.scroll_manager.state.scroll_position = 0
        self.app.state["panel"] = "outline" if self.show_outline and layout.outline else ""
        self.app.state["message"] = ""
        self._after_render(lambda: self.app.focus_element_by_id("body"))

    def _toggle_files(self) -> None:
        if self.files is None:
            self.app.state["message"] = "No file tree: give all2md read a folder or a pattern"
            return
        if self.app.state.get("panel") == "files":
            self.app.state["panel"] = ""
            return
        self.app.state["panel"] = "files"
        if self.current is not None and self.current in self.files.files:
            expanded = set(self.app.state.get("files_expanded") or [])
            self.app.state["files_expanded"] = sorted(expanded | set(self.files.folder_ids(self.current)))
        self._after_render(self._mark_current)

    def _mark_current(self) -> None:
        """Focus the file tree, with the open file highlighted and in view."""
        tree: Any = self.app.get_element_by_id("files")
        if tree is None or self.files is None:
            return
        self.app.focus_element_by_id("files")
        if self.current is None or self.current not in self.files.files:
            return
        node_id = self.files.node_id(self.current)
        for index, info in enumerate(tree.nodes):
            if info["node"]["id"] == node_id:
                tree.selected_node_id = node_id
                tree.highlighted_index = index
                tree.scroll_manager.scroll_to(max(0, index - tree.scroll_manager.state.viewport_size // 2))
                break

    def _after_render(self, then: Callable[[], Any]) -> None:
        """Render now, then call ``then`` on the elements just built.

        Wijjit has no hook after a render, and a tree shown again is a new
        element that has forgotten its highlight, so the viewer renders itself
        (``_render`` is internal to Wijjit; ``wijjit<0.2`` is pinned). wijjit#94 asks for a
        public way.
        """
        self.app._render()
        then()

    def _copy(self) -> None:
        if not self.shown_target:
            self.app.state["message"] = "No link to copy: choose an external link first"
            return
        try:
            import pyperclip

            pyperclip.copy(self.shown_target)
        except Exception as error:  # pyperclip raises its own types when no clipboard is found
            self.app.state["message"] = f"Could not copy ({error.__class__.__name__}): {self.shown_target}"
            return
        self.app.state["message"] = f"Copied: {self.shown_target}"

    def _on_outline_select(self, event: Any) -> None:
        node = getattr(event, "data", None) or {}
        node_id = str(node.get("id", ""))
        if node_id.startswith("h") and self.width is not None:
            line = self.layout.heading_line(int(node_id[1:]), self.width)
            if line is not None:
                self.jump(line)
                self.app.refresh()

    def _on_link_select(self, event: Any) -> None:
        node = getattr(event, "data", None) or {}
        node_id = str(node.get("id", ""))
        if node_id.startswith("l") and self.width is not None:
            index = int(node_id[1:])
            for position in self.layout.at(self.width).links:
                if position.index == index:
                    self.follow(position)
                    break
            self.app.refresh()

    def _on_file_select(self, event: Any) -> None:
        node = getattr(event, "data", None) or {}
        path = self.files.path_of(str(node.get("id", ""))) if self.files is not None else None
        if path is not None:
            self.open(path)
            self.app.refresh()

    def _on_body_click(self, event: Any) -> None:
        data = getattr(event, "data", None) or {}
        line, column = data.get("line"), data.get("column")
        if line is None or column is None or self.width is None:
            return
        for position in self.layout.at(self.width).links:
            if position.line == line and position.start <= column < position.end:
                self.follow(position)
                self.app.refresh()
                return


_SCROLLS: dict[Action, Callable[[int], int]] = {
    Action.LINE_DOWN: lambda height: 1,
    Action.LINE_UP: lambda height: -1,
    Action.PAGE_DOWN: lambda height: max(1, height - 1),
    Action.PAGE_UP: lambda height: -max(1, height - 1),
    Action.HALF_PAGE_DOWN: lambda height: max(1, height // 2),
    Action.HALF_PAGE_UP: lambda height: -max(1, height // 2),
}


def _root(children: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap tree nodes in the (hidden) root node Wijjit's tree expects."""
    return {"id": "root", "label": "", "children": children}


def _outline_nodes(entries: tuple[OutlineEntry, ...]) -> list[dict[str, Any]]:
    return [
        {"id": f"h{entry.index}", "label": entry.text, "children": _outline_nodes(entry.children)} for entry in entries
    ]


def _placeholder(files: Optional[FileTree]) -> DocumentLayout:
    """Lay out the note the body shows before a file is chosen."""
    from all2md.ast import Document, Paragraph, Text
    from all2md.options.terminal import TerminalRendererOptions

    if files is not None and not files.files:
        note = f"No documents all2md can read were found in {files.root}."
    else:
        note = "Choose a document in the file tree: arrows move, Enter opens a folder or a file."
    return DocumentLayout(Document(children=[Paragraph(content=[Text(content=note)])]), TerminalRendererOptions())

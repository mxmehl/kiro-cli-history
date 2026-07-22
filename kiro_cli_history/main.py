"""kiro-history: Fuzzy-search and browse Kiro CLI conversation history.

A terminal UI for searching, browsing, and resuming Kiro CLI sessions.
Reads from three stores (all read-only, never modifies session data):
  1. ~/.kiro/sessions/cli/*.json+jsonl (v3: JSONL format, used by --classic mode)
  2. ~/Library/.../kiro-cli/data.sqlite3 conversations_v2 (v2: SQLite, new TUI mode)
  3. ~/Library/.../kiro-cli/data.sqlite3 conversations (v1: SQLite, legacy)
"""

import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from rich.markdown import Markdown
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, RichLog, Static

# --- Data Layer (read-only) ---

# Paths — override with KIRO_DEMO_DIR env var for demo/recording
_DEMO_DIR = os.environ.get("KIRO_DEMO_DIR", "")
SESSIONS_DIR = (
    Path(_DEMO_DIR) / "kiro" / "sessions" / "cli"
    if _DEMO_DIR
    else Path.home() / ".kiro" / "sessions" / "cli"
)
SQLITE_DB = (
    Path(_DEMO_DIR) / "kiro-cli" / "data.sqlite3"
    if _DEMO_DIR
    else Path.home() / "Library" / "Application Support" / "kiro-cli" / "data.sqlite3"
)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB guard
_MINUTES_PER_HOUR = 60


def _format_duration(dur: int) -> str:
    """Format a duration in minutes as e.g. '5m' or '1h 30m'."""
    if dur < _MINUTES_PER_HOUR:
        return f"{dur}m"
    return f"{dur // _MINUTES_PER_HOUR}h {dur % _MINUTES_PER_HOUR}m"


def _extract_prompt(entry: dict) -> str | None:
    """Return the user prompt text of a history entry, if any."""
    content = entry.get("user", {}).get("content", {})
    if "Prompt" in content:
        return content["Prompt"].get("prompt", "")
    return None


def _extract_assistant_text(assistant: dict) -> str | None:
    """Return the assistant reply text of a history entry, if any."""
    if not isinstance(assistant, dict):
        return None
    a_content = assistant.get("content", {})
    if "Text" in a_content:
        return a_content["Text"]
    if "Response" in assistant:
        resp = assistant["Response"]
        if isinstance(resp, dict) and resp.get("content"):
            return resp["content"]
    if "ToolUse" in assistant:
        tu = assistant["ToolUse"]
        if isinstance(tu, dict):
            txt = tu.get("content", "") or ""
            tools = tu.get("tool_uses", [])
            tool_names = ", ".join(t.get("name", "?") for t in tools[:3]) if tools else ""
            if tool_names:
                return f"{txt}\n[tools: {tool_names}]" if txt else f"[tools: {tool_names}]"
            return txt or None
    return None


def _extract_messages_from_history(
    history: list[dict], limit: int | None = None
) -> list[dict[str, str]]:
    """Extract messages from a SQLite v1/v2 history array."""
    messages = []
    for entry in history:
        prompt_text = _extract_prompt(entry)
        if prompt_text:
            messages.append({"role": "you", "text": prompt_text})
            if limit and len(messages) >= limit:
                return messages
        reply_text = _extract_assistant_text(entry.get("assistant", {}))
        if reply_text:
            messages.append({"role": "kiro", "text": reply_text})
            if limit and len(messages) >= limit:
                return messages
    return messages


def _get_first_prompt_from_history(history: list[dict]) -> str:
    """Get the first user prompt from a history array for use as title."""
    for entry in history:
        prompt_text = (_extract_prompt(entry) or "").strip()
        if prompt_text:
            return prompt_text[:60]
    return "(untitled)"


def _parse_v2_row(
    cwd: str, conv_id: str, value: str, created_ms: int, updated_ms: int
) -> dict | None:
    """Parse a single conversations_v2 row into a session dict, or None if invalid."""
    try:
        d = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    history = d.get("history", [])
    created = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    updated = datetime.fromtimestamp(updated_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    return {
        "session_id": conv_id,
        "title": _get_first_prompt_from_history(history),
        "cwd": cwd,
        "created_at": created,
        "updated_at": updated,
        "source": "sqlite_v2",
        "msg_count": len(history),
        "duration_min": int((updated_ms - created_ms) / 1000 / 60),
        "_history": history,
    }


def _parse_v1_row(cwd: str, value: str) -> dict | None:
    """Parse a single legacy conversations row into a session dict, or None if invalid."""
    try:
        d = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    history = d.get("history", [])
    return {
        "session_id": d.get("conversation_id", ""),
        "title": _get_first_prompt_from_history(history),
        "cwd": cwd,
        "created_at": "",
        "updated_at": "",
        "source": "sqlite_v1",
        "msg_count": len(history),
        "duration_min": 0,
        "_history": history,
    }


def _load_sqlite_sessions() -> list[dict]:
    """Load sessions from the SQLite database (v1 + v2 tables)."""
    sessions: list[dict] = []
    if not SQLITE_DB.exists():
        return sessions

    try:
        conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return sessions

    # V2 sessions (Dec 2025 - Mar 2026) — have timestamps and session IDs
    try:
        rows = conn.execute(
            "SELECT key, conversation_id, value, created_at, updated_at "
            "FROM conversations_v2 ORDER BY updated_at DESC"
        ).fetchall()
        sessions.extend(
            filter(None, (_parse_v2_row(*row) for row in rows)),
        )
    except sqlite3.OperationalError:
        pass

    # V1 sessions (Nov 2025 - Dec 2025) — keyed by directory, no timestamps
    try:
        rows = conn.execute("SELECT key, value FROM conversations").fetchall()
        sessions.extend(
            filter(None, (_parse_v1_row(*row) for row in rows)),
        )
    except sqlite3.OperationalError:
        pass

    conn.close()
    return sessions


def _count_jsonl_messages(jsonl_path: Path) -> int:
    """Count Prompt/AssistantMessage lines in a JSONL session file."""
    if not jsonl_path.exists():
        return 0
    count = 0
    with jsonl_path.open() as jf:
        for line in jf:
            try:
                ld = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if ld.get("kind") in ("Prompt", "AssistantMessage"):
                count += 1
    return count


def _compute_duration_min(created: str, updated: str) -> int:
    """Compute the duration in minutes between two ISO timestamps."""
    if not (created and updated):
        return 0
    try:
        c = datetime.fromisoformat(created.replace("Z", "+00:00"))
        u = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    return int((u - c).total_seconds() / 60)


def _load_one_jsonl_session(json_file: Path) -> dict | None:
    """Load a single v3 session from its .json metadata file, or None if invalid."""
    if json_file.stat().st_size > MAX_FILE_SIZE:
        return None
    try:
        with json_file.open() as f:
            meta = json.load(f)
    except (json.JSONDecodeError, ValueError, OSError):
        return None

    created = meta.get("created_at") or ""
    updated = meta.get("updated_at") or ""
    jsonl_path = json_file.with_suffix(".jsonl")
    return {
        "session_id": meta.get("session_id", ""),
        "title": meta.get("title") or "(untitled)",
        "cwd": meta.get("cwd") or "",
        "created_at": created,
        "updated_at": updated,
        "source": "jsonl",
        "msg_count": _count_jsonl_messages(jsonl_path),
        "duration_min": _compute_duration_min(created, updated),
        "jsonl_path": str(jsonl_path),
    }


def _load_jsonl_sessions() -> list[dict]:
    """Load sessions from ~/.kiro/sessions/cli/*.json (v3: current format)."""
    if not SESSIONS_DIR.exists():
        return []
    return list(filter(None, (_load_one_jsonl_session(f) for f in SESSIONS_DIR.glob("*.json"))))


def get_sessions() -> list[dict]:
    """Load all sessions from all stores, deduplicated, sorted by recency."""
    jsonl = _load_jsonl_sessions()
    sqlite = _load_sqlite_sessions()

    # Deduplicate: if same session_id exists in both, prefer JSONL (newer format)
    seen_ids = {s["session_id"] for s in jsonl if s["session_id"]}
    for s in sqlite:
        if s["session_id"] and s["session_id"] not in seen_ids:
            jsonl.append(s)
            seen_ids.add(s["session_id"])

    # Sort: sessions with timestamps first (descending), then untimed ones at the end
    jsonl.sort(key=lambda s: s.get("updated_at") or s.get("created_at") or "0", reverse=True)
    return jsonl


def _text_block_from_content(content: object) -> str:
    """Return the first text block's data from a JSONL content list, or empty string."""
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("kind") == "text":
            data = block.get("data", "")
            return data if isinstance(data, str) else ""
    return ""


def _parse_jsonl_message_line(line: str) -> dict[str, str] | None:
    """Parse one JSONL line into a {role, text} message, or None if not applicable."""
    try:
        d = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    kind = d.get("kind", "")
    if kind not in ("Prompt", "AssistantMessage"):
        return None
    txt = _text_block_from_content(d.get("data", {}).get("content", []))
    if not txt:
        return None
    return {"role": "you" if kind == "Prompt" else "kiro", "text": txt}


def extract_messages(session: dict, limit: int | None = None) -> list[dict[str, str]]:
    """Extract conversation messages from any session format."""
    # SQLite sessions carry _history inline
    if "_history" in session:
        return _extract_messages_from_history(session["_history"], limit)

    # JSONL sessions read from file
    jsonl_path = session.get("jsonl_path", "")
    if not jsonl_path:
        return []
    path = Path(jsonl_path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    if path.stat().st_size > MAX_FILE_SIZE:
        return [{"role": "system", "text": "(File too large to preview)"}]

    messages = []
    with path.open() as f:
        for line in f:
            message = _parse_jsonl_message_line(line)
            if message:
                messages.append(message)
                if limit and len(messages) >= limit:
                    break
    return messages


def _fuzzy_match(query: str, text: str) -> bool:
    """Fuzzy match: all query tokens must appear in text, in any order.

    Supports multi-word queries ('mem leak' matches 'Debug memory leak')
    and tolerates partial words ('depl' matches 'deployment').
    """
    text_lower = text.lower()
    tokens = query.lower().split()
    return all(token in text_lower for token in tokens)


def _session_content_matches(query: str, session: dict) -> bool:
    """Check whether any message in a session's conversation matches the query."""
    return any(_fuzzy_match(query, msg["text"]) for msg in extract_messages(session))


def search_sessions(query: str, sessions: list[dict]) -> list[dict]:
    """Fuzzy-search sessions by title, cwd, and conversation content across all stores."""
    if not query:
        return sessions

    results = []
    for session in sessions:
        title = session.get("title") or ""
        cwd = session.get("cwd") or ""
        if (
            _fuzzy_match(query, title)
            or _fuzzy_match(query, cwd)
            or _session_content_matches(query, session)
        ):
            results.append(session)

    return results


# --- UI Components ---


class SessionItem(ListItem):
    """A single session row in the list."""

    def __init__(self, session: dict) -> None:
        """Store the session dict this row represents."""
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        """Render the row's title, directory, timestamp, message count, and duration."""
        raw_ts = (self.session.get("updated_at") or "")[:10]
        try:
            dt = datetime.strptime(raw_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            ts = dt.strftime("%-d %b %Y")
        except (ValueError, TypeError):
            ts = raw_ts
        title = (self.session.get("title") or "(untitled)")[:60]
        cwd = Path(self.session.get("cwd") or "").name
        msgs = self.session.get("msg_count", 0)
        dur_str = _format_duration(self.session.get("duration_min", 0))
        yield Static(
            f"[bold]{title}[/bold]\n"
            f"[dim]{cwd}[/dim]  [dim italic]{ts}[/dim italic]  "
            f"[dim cyan]{msgs} msgs[/dim cyan]  [dim green]{dur_str}[/dim green]",
            markup=True,
        )


class KiroHistory(App):
    """Kiro CLI session browser and search."""

    TITLE = "kiro-cli-history"
    CSS = """
    Screen {
        layout: horizontal;
    }
    #left-pane {
        width: 2fr;
        min-width: 40;
        border-right: solid $accent;
    }
    #right-pane {
        width: 3fr;
        min-width: 50;
    }
    #search-input {
        dock: top;
        margin: 0 1;
    }
    #session-list {
        height: 1fr;
    }
    #preview {
        height: 1fr;
        padding: 0 1;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    SessionItem {
        padding: 0 1;
        height: 3;
    }
    SessionItem:hover {
        background: $boost;
    }
    ListView > SessionItem.-highlight {
        background: $accent;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+r", "resume", "Resume session"),
        Binding("ctrl+y", "copy_conversation", "Copy to clipboard"),
        Binding("ctrl+f", "search_content", "Search in conversation"),
        Binding("escape", "clear_or_quit", "Clear / Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("/", "focus_search", "Search"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self) -> None:
        """Initialise session state."""
        super().__init__()
        self.all_sessions: list[dict] = []
        self.filtered_sessions: list[dict] = []
        self.selected_session: dict | None = None
        self._viewer_search_query = ""

    def compose(self) -> ComposeResult:
        """Build the search input, session list, and preview pane layout."""
        yield Header()
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Input(placeholder="Search sessions...", id="search-input")
                yield ListView(id="session-list")
            with Vertical(id="right-pane"):
                yield RichLog(id="preview", wrap=True, highlight=True, markup=True)
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Load all sessions and populate the list on startup."""
        self.all_sessions = get_sessions()
        self.filtered_sessions = self.all_sessions
        self._populate_list(self.filtered_sessions)
        status = self.query_one("#status-bar", Static)
        status.update(f" {len(self.all_sessions)} sessions | Ctrl+R resume | / search | ? help")

    def _populate_list(self, sessions: list[dict]) -> None:
        """Replace the session list view's contents."""
        list_view = self.query_one("#session-list", ListView)
        list_view.clear()
        for session in sessions:
            list_view.append(SessionItem(session))

    # --- Search ---

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Trigger a background search when the search input changes."""
        self._do_search(event.value)

    @work(thread=True)
    def _do_search(self, query: str) -> None:
        """Run a fuzzy search in the background and refresh the session list."""
        results = search_sessions(query, self.all_sessions)
        self.filtered_sessions = results
        self.call_from_thread(self._populate_list, results)
        status_text = f" {len(results)}/{len(self.all_sessions)} sessions"
        if query:
            status_text += f" matching '{query}'"
        status_text += " | Ctrl+R resume | / search"
        self.call_from_thread(self.query_one("#status-bar", Static).update, status_text)

    # --- Preview ---

    @on(ListView.Highlighted, "#session-list")
    def on_session_highlighted(self, event: ListView.Highlighted) -> None:
        """Load the preview pane for the newly highlighted session."""
        if not isinstance(event.item, SessionItem):
            return
        session = event.item.session
        self.selected_session = session
        self._load_preview(session)

    @work(thread=True)
    def _load_preview(self, session: dict) -> None:
        """Render a session's metadata header and full conversation into the preview pane."""
        preview = self.query_one("#preview", RichLog)
        self.call_from_thread(preview.clear)

        # Header
        title = session.get("title") or "(untitled)"
        cwd = session.get("cwd") or ""
        created = (session.get("created_at") or "")[:19].replace("T", " ")
        updated = (session.get("updated_at") or "")[:19].replace("T", " ")
        msgs = session.get("msg_count", 0)
        dur_str = _format_duration(session.get("duration_min", 0))

        header = (
            f"[bold]SESSION:[/bold] {title}\n"
            f"[bold]DIRECTORY:[/bold] {cwd}\n"
            f"[bold]CREATED:[/bold] {created}\n"
            f"[bold]UPDATED:[/bold] {updated}\n"
            f"[bold]MESSAGES:[/bold] {msgs}\n"
            f"[bold]DURATION:[/bold] {dur_str}\n"
            f"[bold]ID:[/bold] {session.get('session_id', '')}\n"
        )
        self.call_from_thread(preview.write, Text.from_markup(header))
        self.call_from_thread(preview.write, Text("─" * 50))
        self.call_from_thread(preview.write, Text(""))

        # Messages
        messages = extract_messages(session)
        if not messages:
            self.call_from_thread(preview.write, Text("(no conversation data)"))
            return

        for msg in messages:
            role = msg["role"]
            txt = msg["text"]
            if role == "you":
                label = Text.from_markup("[bold cyan][YOU]:[/bold cyan]")
            else:
                label = Text.from_markup("[bold green][KIRO]:[/bold green]")
            self.call_from_thread(preview.write, label)
            # Try to render as markdown for assistant messages
            if role == "kiro":
                try:
                    self.call_from_thread(preview.write, Markdown(txt))
                except Exception:  # noqa: BLE001 - rich's markdown parser error surface
                    # is undocumented; fall back to plain text rather than crash the worker.
                    self.call_from_thread(preview.write, Text(txt))
            else:
                self.call_from_thread(preview.write, Text(txt))
            self.call_from_thread(preview.write, Text(""))

    # --- Actions ---

    def action_resume(self) -> None:
        """Exit the app and signal the entry point to resume the selected session."""
        if not self.selected_session:
            return
        cwd = self.selected_session.get("cwd", "")
        if not cwd or not Path(cwd).is_dir():
            self.notify(f"Directory not found: {cwd}", severity="error")
            return
        self.exit(result=("resume", self.selected_session))

    def action_focus_search(self) -> None:
        """Move focus to the search input."""
        self.query_one("#search-input", Input).focus()

    def action_clear_or_quit(self) -> None:
        """Clear the search input, or quit the app if it is already empty."""
        search = self.query_one("#search-input", Input)
        if search.value:
            search.value = ""
            search.focus()
        else:
            self.exit()

    def action_cursor_down(self) -> None:
        """Move the session list cursor down."""
        self.query_one("#session-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the session list cursor up."""
        self.query_one("#session-list", ListView).action_cursor_up()

    def action_search_content(self) -> None:
        """Move focus to the search input."""
        self.query_one("#search-input", Input).focus()

    def action_copy_conversation(self) -> None:
        """Copy the selected session's full conversation to the clipboard."""
        if not self.selected_session:
            return
        messages = extract_messages(self.selected_session)
        if not messages:
            self.notify("No messages to copy", severity="warning")
            return
        text = ""
        for msg in messages:
            label = "[YOU]" if msg["role"] == "you" else "[KIRO]"
            text += f"{label}:\n{msg['text']}\n\n"
        pbcopy = shutil.which("pbcopy")
        if not pbcopy:
            self.notify("pbcopy not found (macOS only)", severity="error")
            return
        subprocess.run([pbcopy], input=text.encode("utf-8"), check=True)  # noqa: S603
        self.notify(f"Copied {len(messages)} messages to clipboard")


# --- Entry Point ---


def main() -> None:
    """Run the TUI and, if the user requested it, resume a session afterwards."""
    app = KiroHistory()
    result = app.run()

    if result and isinstance(result, tuple) and result[0] == "resume":
        session = result[1]
        cwd = session["cwd"]
        print(f"\nResuming session: {session['title']}")
        print(f"Directory: {cwd}\n")
        os.chdir(cwd)
        kiro_cli = shutil.which("kiro-cli")
        if not kiro_cli:
            print("kiro-cli not found on PATH.")
            return
        session_id = session.get("session_id", "")
        args = (
            ["kiro-cli", "chat", "--resume-id", session_id]
            if session_id
            else ["kiro-cli", "chat", "--resume"]
        )
        os.execv(kiro_cli, args)  # noqa: S606


if __name__ == "__main__":
    main()

<!--
SPDX-License-Identifier: MIT
SPDX-FileCopyrightText: 2026 Prabhu G <gangprab@amazon.com>
SPDX-FileCopyrightText: 2026 Max Mehl <https://mehl.mx>
-->

# kiro-cli-history

![kiro-cli-history demo](/meta/demo.gif)

A terminal UI for fuzzy-searching, browsing, and resuming [Kiro CLI](https://kiro.dev/docs/cli/) conversations.

## The problem

Kiro CLI has great built-in [conversation persistence](https://kiro.dev/docs/cli/chat/#conversation-persistence) — it saves your sessions and lets you resume them with `--resume` and `--resume-picker`. However, these are scoped to the directory where the session was started. If you work across many projects and directories, finding a specific past conversation means remembering which folder you were in at the time.

`kiro-cli-history` complements Kiro CLI's native persistence by adding **global fuzzy search across all sessions** — regardless of which directory they were started in. It searches the full content of every message exchanged, not just session titles.

## What it offers

- **Global search** — find conversations across all directories, not just the current one
- **Full-text fuzzy search** — searches every message you and Kiro exchanged, not just titles
- **Conversation preview** — read through the full exchange with markdown rendering before deciding to resume
- **Session metadata** — see the working directory, last activity date, message count, duration - including total credit usage!
- **One-key resume** — press `Ctrl+R` to jump into Kiro CLI and continue the conversation
- **Copy to clipboard** — press `Ctrl+Y` to copy an entire conversation
- **All session formats** — reads all four Kiro CLI storage versions (CLI 1.x SQLite, CLI 2.x SQLite, CLI 2.x classic-mode JSONL, CLI 3.0), covering both `--classic` and TUI modes across versions

## Read-only

This tool **never writes to or modifies** your Kiro CLI session data. It only reads from:
- `~/.kiro/sessions/<workspace-hash>/sess_*/` (CLI 3.0 sessions)
- `~/.kiro/sessions/cli/` (CLI 2.x classic-mode JSONL sessions)
- The Kiro CLI SQLite database (`data.sqlite3`), opened in read-only mode — located at `~/Library/Application Support/kiro-cli/` on macOS, `~/.local/share/kiro-cli/` on Linux, or `%APPDATA%\kiro-cli\` on Windows

## Install

Requires at least Python 3.10.

With [pipx](https://pipx.pypa.io/):

```bash
pipx install kiro-cli-history
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv tool install kiro-cli-history
```

With pip:

```bash
pip3 install kiro-cli-history
```

## Usage

```bash
kiro-cli-history
```

Run it from anywhere. It searches globally.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search bar |
| `j` / `k` or arrows | Navigate sessions |
| `Ctrl+R` | Resume the highlighted session in Kiro CLI |
| `Ctrl+Y` | Copy conversation to clipboard |
| `Ctrl+F` | Focus search bar |
| `Esc` | Clear search / Quit |
| `Ctrl+C` | Quit |

### Searching

Type in the search bar to fuzzy-search across:
- Session titles
- Working directories
- Full conversation content (every message exchanged)

Search is case-insensitive and covers all session formats.

### Text selection

Hold **Option (Alt)** while dragging to select text from the preview pane. Or press **Ctrl+Y** to copy the full conversation to clipboard.

### Configuration

Settings are stored in a JSON file managed via the `config` subcommand — no need to edit it by hand.

```bash
kiro-cli-history config show          # print all settings and the config file path
kiro-cli-history config get scroll_top
kiro-cli-history config set scroll_top true
```

Available settings:

| Key | Default | Description |
|-----|---------|--------------|
| `scroll_top` | `false` | Show the start of a conversation in the preview pane instead of jumping to the most recent messages |

The config file lives at the platform's standard config location (e.g. `~/Library/Application Support/kiro-cli-history/config.json` on macOS).

## How it works

Kiro CLI stores conversations in four formats depending on the version and mode:

| Format | Location | Used by |
|--------|----------|---------|
| CLI 3.0 | `~/.kiro/sessions/<workspace-hash>/sess_*/session.json` + `messages.jsonl` | `kiro-cli --v3` |
| CLI 2.x (classic JSONL) | `~/.kiro/sessions/cli/*.json` + `*.jsonl` | `kiro-cli --classic` (2.x) |
| CLI 2.x (SQLite) | Platform data dir (`~/Library/Application Support/kiro-cli/` on macOS, `~/.local/share/kiro-cli/` on Linux, `%APPDATA%\kiro-cli\` on Windows), `data.sqlite3`, `conversations_v2` table | TUI mode (2.x) |
| CLI 1.x (SQLite) | Same database, `conversations` table | Legacy |

`kiro-cli-history` reads all four and presents them in a unified view. Each session shows:
- **Title** — first message or auto-generated title
- **Directory** — where the session was started
- **Date** — last activity (e.g., "7 Apr 2026")
- **Message count** — total exchanges
- **Duration** — elapsed time
- **Credit usage** — total credits spent on the session (CLI 2.x and CLI 3.0 sessions only — SQLite sessions don't record this)

## Comparison with alternatives

Kiro CLI 2.21+ ships its own V3-only session dashboard (`/sessions` or `kiro-cli chat --sessions`), which closed much of the gap this tool originally filled: it can list sessions across all workspaces (toggle off `current workspace only`) and content-search your prompts and the agent's responses, not just titles. `--list-sessions --all-cwds` also lists sessions across directories from the shell, without the TUI.

What the native dashboard still doesn't cover, as of CLI 2.27:

- **Legacy formats**: it only content-indexes local V2 and V3 session transcripts. CLI 1.x SQLite sessions, classic-mode JSONL sessions, and cloud sessions are matched by title/workspace/ID/tag only — their message content isn't searchable
- **Tool output**: never indexed in either native mode
- **Markdown-rendered preview**: the native dashboard has no preview pane at all — you browse a list and press Enter to resume; there's no way to see conversation content before committing
- **Clipboard export**: no equivalent to copying a full conversation to the clipboard
- **Credit usage per session**: not shown in the dashboard
- **V1/V2 harness support**: `/sessions` is V3-only; it's unavailable if you run the legacy terminal UI or classic mode

| | `/sessions` dashboard (native, V3) | `--list-sessions --all-cwds` (native) | `kiro-cli-history` |
|---|---|---|---|
| Scope | All workspaces (toggle) | All directories | All directories |
| Content search | Prompts + responses, local V2/V3 only | None (metadata only) | Full-text, all four storage formats |
| Legacy format support (CLI 1.x, classic JSONL) | Metadata only, no content search | Yes, listing only | Yes, including content search |
| Preview | None (list only, resume to see content) | Session list (JSON/plain) | Rendered markdown conversation |
| Clipboard copy | No | No | Yes (`Ctrl+Y`) |
| Credit usage | No | No | Yes (CLI 2.x/3.0 sessions) |
| Requires V3 | Yes | No | No |

If you're on V3 and mainly care about recent sessions, the native dashboard now covers some day-to-day uses. `kiro-cli-history` remains useful if you're interested in having a credits overview, need to search old CLI 1.x/classic sessions, want a readable markdown preview before resuming, or use V1/V2 harness modes where `/sessions` doesn't exist.

## Platform

Session discovery and clipboard support now work across macOS, Linux, and Windows:
- **Session storage** — resolved via the same platform-specific data directory convention Kiro CLI itself uses (`~/Library/Application Support/`, `~/.local/share/`, or `%APPDATA%`)
- **Clipboard** — tries `pbcopy` (macOS), `clip` (Windows), then `wl-copy`, `xclip`, or `xsel` (Linux, Wayland/X11)

This has been tested on macOS and Windows. Linux support is implemented but not yet verified in practice — bug reports and PRs are welcome if something doesn't work as expected.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup and quality checks. Commits to the default branch follow [Conventional Commits](https://www.conventionalcommits.org/), and releases are automated with [release-please](https://github.com/googleapis/release-please) — see [CHANGELOG.md](CHANGELOG.md) for the release history.

## Credits

Inspired by [raine/claude-history](https://github.com/raine/claude-history) — an excellent fuzzy-search tool for Claude Code conversations. If you use Claude Code, check that out.

Forked from [prabhu-g/kiro-cli-history](https://github.com/prabhugr/kiro-cli-history) — thanks to Prabhu for the initial implementation!

## License

MIT

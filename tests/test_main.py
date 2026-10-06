"""Smoke tests for the core, dependency-free data logic."""

# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Max Mehl <https://mehl.mx>

import json
from pathlib import Path

import pytest

from kiro_cli_history import main as main_module
from kiro_cli_history.main import (
    _copy_to_clipboard,
    _extract_credits_used,
    _extract_messages_from_history,
    _fuzzy_match,
    _get_first_prompt_from_history,
    _load_one_v3_session,
    extract_messages,
    search_sessions,
)
from tests.fixtures import (
    SAMPLE_SESSIONS,
    write_jsonl_session,
    write_sqlite_v2_sessions,
    write_v3_session,
)


def test_jsonl_session_with_non_utf8_safe_bytes_loads_correctly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Classic-mode .json/.jsonl reads must always use UTF-8, regardless of platform locale.

    Regression test for a real-world bug: Kiro CLI always writes session files as UTF-8,
    but on Windows, Path.open() without encoding="utf-8" falls back to the system codepage
    (e.g. cp1252), which cannot decode many valid UTF-8 byte sequences (umlauts, em dashes,
    curly quotes seen in real session exports). This writes a session containing such bytes
    and confirms it loads correctly. It also asserts the five file reads in main.py request
    encoding="utf-8" explicitly, so the bug can't silently resurface on a platform where the
    default encoding happens to match UTF-8 (e.g. macOS/Linux, where this test would
    otherwise pass even without the fix).
    """
    jsonl_root = tmp_path / "cli"
    title = "Ümlaut café — \u201equote\u201c"
    write_jsonl_session(
        jsonl_root,
        title=title,
        cwd="/home/user/na\u00efve",
        messages=[("you", "Kennst du foobarwhatever?"), ("kiro", "Nein — sagt mir nichts.")],
        days_ago=1,
        duration_min=5,
    )
    monkeypatch.setattr(main_module, "SESSIONS_DIR", jsonl_root)

    sessions = main_module._load_jsonl_sessions()  # noqa: SLF001

    assert len(sessions) == 1
    assert sessions[0]["title"] == title
    assert sessions[0]["msg_count"] == 2

    # Structural guard: every Path.open() call in main.py must pin encoding="utf-8",
    # since the runtime failure above can't be reproduced on platforms (macOS/Linux)
    # whose default encoding is already UTF-8.
    source = Path(main_module.__file__).read_text(encoding="utf-8")
    open_calls = [line for line in source.splitlines() if ".open(" in line and "Path" not in line]
    assert open_calls, "expected at least one .open() call in main.py"
    for line in open_calls:
        assert 'encoding="utf-8"' in line, f"missing encoding='utf-8' in: {line.strip()}"


def test_fuzzy_match_tokens_any_order() -> None:
    """All query tokens must appear, order-independent, substrings allowed."""
    assert _fuzzy_match("mem leak", text="Debug memory leak in worker")
    assert _fuzzy_match("depl", "deployment pipeline")
    assert not _fuzzy_match("mem leak", "Deploy the app")


def test_extract_messages_from_history_roundtrip() -> None:
    """Prompt/response pairs from a SQLite-style history are extracted in order."""
    history = [
        {
            "user": {"content": {"Prompt": {"prompt": "hello"}}},
            "assistant": {"content": {"Text": "hi there"}},
        },
        {
            "user": {"content": {"Prompt": {"prompt": "bye"}}},
            "assistant": {"Response": {"content": "goodbye"}},
        },
    ]
    messages = _extract_messages_from_history(history)
    assert messages == [
        {"role": "you", "text": "hello"},
        {"role": "kiro", "text": "hi there"},
        {"role": "you", "text": "bye"},
        {"role": "kiro", "text": "goodbye"},
    ]
    assert _get_first_prompt_from_history(history) == "hello"


def test_search_sessions_matches_title_and_content() -> None:
    """Sessions are matched by title, and by content when title doesn't match."""
    sessions = [
        {
            "title": "Fix deployment bug",
            "cwd": "/repo/a",
            "_history": [{"user": {"content": {"Prompt": {"prompt": "irrelevant"}}}}],
        },
        {
            "title": "Unrelated",
            "cwd": "/repo/b",
            "_history": [{"user": {"content": {"Prompt": {"prompt": "memory leak"}}}}],
        },
    ]
    assert search_sessions("deployment", sessions) == [sessions[0]]
    assert search_sessions("memory leak", sessions) == [sessions[1]]
    assert search_sessions("", sessions) == sessions


def test_extract_credits_used_sums_multiple_turns() -> None:
    """Credits are summed across all turns and all metering_usage entries per turn."""
    meta = {
        "session_state": {
            "conversation_metadata": {
                "user_turn_metadatas": [
                    {
                        "metering_usage": [
                            {"value": 0.1, "unit": "credit"},
                            {"value": 0.2, "unit": "credit"},
                        ]
                    },
                    {"metering_usage": [{"value": 0.3, "unit": "credit"}]},
                ]
            }
        }
    }
    assert _extract_credits_used(meta) == 0.6000000000000001


def test_extract_credits_used_missing_turns_returns_none() -> None:
    """No user_turn_metadatas (missing or empty) means no usage data at all."""
    assert _extract_credits_used({}) is None
    assert _extract_credits_used({"session_state": {}}) is None
    assert (
        _extract_credits_used(
            {"session_state": {"conversation_metadata": {"user_turn_metadatas": []}}}
        )
        is None
    )


def test_extract_credits_used_ignores_non_credit_units() -> None:
    """Only entries with unit == 'credit' are summed; other units are ignored."""
    meta = {
        "session_state": {
            "conversation_metadata": {
                "user_turn_metadatas": [
                    {
                        "metering_usage": [
                            {"value": 5.0, "unit": "token"},
                            {"value": 0.5, "unit": "credit"},
                        ]
                    }
                ]
            }
        }
    }
    assert _extract_credits_used(meta) == 0.5


def test_extract_credits_used_handles_empty_or_missing_metering_usage() -> None:
    """Turns with an empty or absent metering_usage list don't break summation."""
    meta = {
        "session_state": {
            "conversation_metadata": {
                "user_turn_metadatas": [
                    {"metering_usage": []},
                    {},
                    {"metering_usage": [{"value": 1.0, "unit": "credit"}]},
                ]
            }
        }
    }
    assert _extract_credits_used(meta) == 1.0


def test_copy_to_clipboard_uses_first_available_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first available clipboard tool in the priority list is used."""
    calls = []

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name == "wl-copy" else None

    def fake_run(cmd: list[str], input: bytes, check: bool) -> None:  # noqa: A002
        calls.append((cmd, input, check))

    monkeypatch.setattr(main_module.shutil, "which", fake_which)
    monkeypatch.setattr(main_module.subprocess, "run", fake_run)

    assert _copy_to_clipboard("hello") is True
    assert calls == [(["/usr/bin/wl-copy"], b"hello", True)]


def test_copy_to_clipboard_returns_false_when_no_tool_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No clipboard tool on PATH means the function reports failure, not an exception."""
    monkeypatch.setattr(main_module.shutil, "which", lambda _name: None)
    assert _copy_to_clipboard("hello") is False


def _write_v3_session(
    tmp_path: Path, session_id: str = "sess_abc123", cwd: str = "/repo/a"
) -> Path:
    """Create a fixture CLI 3.0 session.json + messages.jsonl on disk and return the dir."""
    session_dir = tmp_path / "workspacehash" / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "session.json").write_text(
        json.dumps(
            {
                "id": session_id,
                "title": "Fix the deploy pipeline",
                "workspacePaths": [cwd],
                "createdAt": "2026-09-08T13:19:33.360Z",
                "lastModifiedAt": "2026-09-08T13:42:47.816Z",
            }
        )
    )
    lines = [
        {"payload": {"type": "tool_call", "toolName": "fetch_cloud_config"}},
        {"payload": {"type": "user", "content": "hello there"}},
        {"payload": {"type": "assistant", "content": "hi, how can I help?"}},
        {
            "payload": {
                "type": "usage_summary",
                "promptTurnSummaries": [{"unit": "credit", "usage": 1.5}],
            }
        },
    ]
    (session_dir / "messages.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n"
    )
    return session_dir


def test_load_one_v3_session_maps_fields(tmp_path: Path) -> None:
    """A CLI 3.0 session.json is mapped to the common session dict shape."""
    session_dir = _write_v3_session(tmp_path, session_id="sess_abc123", cwd="/repo/a")
    session = _load_one_v3_session(session_dir / "session.json")
    assert session is not None
    assert session["session_id"] == "sess_abc123"
    assert session["title"] == "Fix the deploy pipeline"
    assert session["cwd"] == "/repo/a"
    assert session["created_at"] == "2026-09-08T13:19:33.360Z"
    assert session["updated_at"] == "2026-09-08T13:42:47.816Z"
    assert session["source"] == "v3"
    assert session["msg_count"] == 2  # only user/assistant lines counted, not tool_call
    assert session["credits_used"] == 1.5
    assert session["messages_path"] == str(session_dir / "messages.jsonl")


def test_load_one_v3_session_returns_none_for_invalid_json(tmp_path: Path) -> None:
    """A corrupt session.json is skipped rather than raising."""
    bad_file = tmp_path / "session.json"
    bad_file.write_text("{not valid json")
    assert _load_one_v3_session(bad_file) is None


def test_extract_messages_v3_roundtrip(tmp_path: Path) -> None:
    """extract_messages reads a CLI 3.0 messages.jsonl, skipping non-user/assistant lines."""
    session_dir = _write_v3_session(tmp_path)
    session = _load_one_v3_session(session_dir / "session.json")
    assert extract_messages(session) == [
        {"role": "you", "text": "hello there"},
        {"role": "kiro", "text": "hi, how can I help?"},
    ]


def test_load_one_v3_session_no_usage_data_returns_none(tmp_path: Path) -> None:
    """Sessions with no usage_summary lines report credits_used as None, not 0.0."""
    session_dir = tmp_path / "workspacehash" / "sess_no_usage"
    session_dir.mkdir(parents=True)
    (session_dir / "session.json").write_text(
        json.dumps(
            {
                "id": "sess_no_usage",
                "title": "No usage data",
                "workspacePaths": ["/repo/b"],
                "createdAt": "2026-09-08T13:19:33.360Z",
                "lastModifiedAt": "2026-09-08T13:42:47.816Z",
            }
        )
    )
    (session_dir / "messages.jsonl").write_text(
        json.dumps({"payload": {"type": "user", "content": "hi"}}) + "\n"
    )
    session = _load_one_v3_session(session_dir / "session.json")
    assert session is not None
    assert session["credits_used"] is None


def test_get_sessions_reads_all_formats_from_shared_demo_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_sessions() finds every session written in the v3, classic, and sqlite formats.

    Uses the same sample data as demo/generate_demo_data.py (tests/fixtures.py) so the
    demo dataset doubles as an integration fixture for the three on-disk formats.
    """
    v3_root = tmp_path / "kiro" / "sessions"
    jsonl_root = v3_root / "cli"
    sqlite_path = tmp_path / "kiro-cli" / "data.sqlite3"

    v3_sessions = SAMPLE_SESSIONS[:2]
    jsonl_sessions = SAMPLE_SESSIONS[2:4]
    sqlite_sessions = SAMPLE_SESSIONS[4:6]

    for title, cwd, messages, days_ago, duration_min in v3_sessions:
        write_v3_session(v3_root, title, cwd, messages, days_ago, duration_min)
    for title, cwd, messages, days_ago, duration_min in jsonl_sessions:
        write_jsonl_session(jsonl_root, title, cwd, messages, days_ago, duration_min)
    write_sqlite_v2_sessions(sqlite_path, sqlite_sessions)

    # SESSIONS_DIR doubles as the classic-mode root and (via .parent) the v3 root.
    monkeypatch.setattr(main_module, "SESSIONS_DIR", jsonl_root)
    monkeypatch.setattr(main_module, "SQLITE_DB", sqlite_path)

    sessions = main_module.get_sessions()
    titles = {s["title"] for s in sessions}
    sources = {s["source"] for s in sessions}

    assert len(sessions) == 6
    assert sources == {"v3", "jsonl", "sqlite_v2"}
    for title, *_ in v3_sessions + jsonl_sessions:
        assert title in titles
    # sqlite_v2 sessions have no title field; they fall back to the first prompt,
    # truncated to 60 chars (see _get_first_prompt_from_history).
    for _, _, messages, _, _ in sqlite_sessions:
        assert messages[0][1][:60] in titles

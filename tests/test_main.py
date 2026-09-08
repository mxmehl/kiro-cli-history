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

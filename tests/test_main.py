"""Smoke tests for the core, dependency-free data logic."""

from kiro_cli_history.main import (
    _extract_credits_used,
    _extract_messages_from_history,
    _fuzzy_match,
    _get_first_prompt_from_history,
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

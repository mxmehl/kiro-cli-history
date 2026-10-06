#!/usr/bin/env python3
"""Generate synthetic Kiro CLI session data for demo recording.

Writes fake sessions in all three on-disk formats kiro-cli-history reads
(CLI 3.0, CLI 2.x classic JSONL, and CLI 2.x SQLite) under demo/data/, using
the same sample conversations as the test suite (see tests/fixtures.py).

Usage:
    uv run python demo/generate_demo_data.py
    KIRO_DEMO_DIR=demo/data uv run kiro-cli-history
"""

# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Max Mehl <https://mehl.mx>

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.fixtures import (
    SAMPLE_SESSIONS,
    write_jsonl_session,
    write_sqlite_v2_sessions,
    write_v3_session,
)

DEMO_DIR = Path(__file__).parent / "data"


def main() -> None:
    """Regenerate demo/data/ from scratch using the shared sample sessions."""
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)

    v3_root = DEMO_DIR / "kiro" / "sessions"
    jsonl_root = DEMO_DIR / "kiro" / "sessions" / "cli"
    sqlite_path = DEMO_DIR / "kiro-cli" / "data.sqlite3"

    # Spread the sample sessions across all three formats so the demo (and any
    # manual testing against KIRO_DEMO_DIR) exercises every code path.
    thirds = len(SAMPLE_SESSIONS) // 3
    v3_sessions = SAMPLE_SESSIONS[:thirds]
    jsonl_sessions = SAMPLE_SESSIONS[thirds : 2 * thirds]
    sqlite_sessions = SAMPLE_SESSIONS[2 * thirds :]

    for title, cwd, messages, days_ago, duration_min in v3_sessions:
        write_v3_session(v3_root, title, cwd, messages, days_ago, duration_min)

    for title, cwd, messages, days_ago, duration_min in jsonl_sessions:
        write_jsonl_session(jsonl_root, title, cwd, messages, days_ago, duration_min)

    write_sqlite_v2_sessions(sqlite_path, sqlite_sessions)

    print(f"Demo data created in: {DEMO_DIR}")
    print(f"  CLI 3.0 sessions:   {v3_root} ({len(v3_sessions)})")
    print(f"  Classic sessions:   {jsonl_root} ({len(jsonl_sessions)})")
    print(f"  SQLite sessions:    {sqlite_path} ({len(sqlite_sessions)})")
    print()
    print("To run with demo data:")
    print(f"  KIRO_DEMO_DIR={DEMO_DIR} uv run kiro-cli-history")


if __name__ == "__main__":
    main()

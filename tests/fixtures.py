"""Shared synthetic session data and on-disk writers for all four storage formats.

This module is the single source of truth for realistic (but fake) Kiro CLI
session content. It is used both by the pytest suite (`test_main.py`) and by
`demo/generate_demo_data.py` to populate the data used for recording the README
GIF, so the two stay in sync automatically.
"""

# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Max Mehl <https://mehl.mx>

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Each entry: (title, cwd, [(role, text), ...], days_ago, duration_min)
# "role" is "you" or "kiro". Lines starting with "[tools: ...]" render as a tool-use step.
SAMPLE_SESSIONS: list[tuple[str, str, list[tuple[str, str]], int, int]] = [
    (
        "Deploy FastAPI app to ECS Fargate",
        "/Users/demo/projects/weather-api",
        [
            ("you", "I have a FastAPI app that I want to deploy to ECS Fargate."),
            ("kiro", "Sure! Let me look at your project structure first."),
            ("kiro", "[tools: fs_read]"),
            (
                "kiro",
                (
                    "I can see your FastAPI app with a Dockerfile. Let me create the ECS task "
                    "definition, service, and ALB configuration."
                ),
            ),
            ("you", "Sounds good. Also add a CloudWatch dashboard for monitoring."),
            ("kiro", "I'll add CloudWatch alarms for CPU, memory, and 5xx errors."),
        ],
        1,
        25,
    ),
    (
        "Fix CORS issue in React + API Gateway",
        "/Users/demo/projects/dashboard-frontend",
        [
            ("you", "My React app is getting CORS errors calling my API Gateway endpoint."),
            ("kiro", "Let me check your API Gateway configuration."),
            ("kiro", "[tools: fs_read]"),
            (
                "kiro",
                (
                    "Found it: the OPTIONS preflight method is missing CORS headers. Fixing "
                    "the API Gateway resource and the Lambda response now."
                ),
            ),
            ("you", "Why does it work in Postman but not in the browser?"),
            ("kiro", "Postman doesn't enforce CORS — it's a browser-only mechanism."),
        ],
        3,
        12,
    ),
    (
        "Set up CI/CD pipeline with GitHub Actions",
        "/Users/demo/projects/saas-platform",
        [
            ("you", "Create a GitHub Actions workflow for our Node.js monorepo."),
            ("kiro", "I'll check what packages you have first."),
            ("kiro", "[tools: code]"),
            (
                "kiro",
                (
                    "Found 4 packages: api, web, shared, worker. Setting up path-based "
                    "triggers, parallel test jobs, and a staging deploy on merge."
                ),
            ),
            ("you", "Can you add a preview deployment for each PR using Vercel?"),
            ("kiro", "Added — it comments the preview URL on the PR."),
        ],
        5,
        35,
    ),
    (
        "Analyze CloudWatch logs for Lambda timeout",
        "/Users/demo/projects/data-pipeline",
        [
            ("you", "Our Lambda function is timing out intermittently."),
            ("kiro", "Let me check the CloudWatch logs and function configuration."),
            ("kiro", "[tools: code]"),
            (
                "kiro",
                (
                    "Found it: a full table scan happens when the status field is missing "
                    "from the event, about 15% of the time. Adding a GSI should fix this."
                ),
            ),
            ("you", "How much would the GSI cost?"),
            ("kiro", "Roughly $3.60/month total — cheaper than the current timeout retries."),
        ],
        7,
        18,
    ),
    (
        "Migrate PostgreSQL to Aurora Serverless v2",
        "/Users/demo/projects/backend-services",
        [
            ("you", "We want to migrate self-managed PostgreSQL on EC2 to Aurora Serverless v2."),
            (
                "kiro",
                (
                    "Good choice. I'll use DMS for continuous replication, then validate "
                    "and switch over during a maintenance window."
                ),
            ),
            ("you", "We're on PostgreSQL 12. Is that a problem?"),
            ("kiro", "Yes, PG 12 is EOL. Upgrade to PG 15 on EC2 first, then migrate."),
            ("you", "What about PostGIS, pg_cron, and pgvector?"),
            ("kiro", "All three are supported on Aurora PG 15 — no blockers there."),
        ],
        14,
        42,
    ),
    (
        "Write unit tests for authentication middleware",
        "/Users/demo/projects/auth-service",
        [
            ("you", "Help me write unit tests for our JWT authentication middleware."),
            ("kiro", "Let me read the middleware code first."),
            ("kiro", "[tools: fs_read]"),
            (
                "kiro",
                (
                    "I'll cover: valid token, missing token, expired token, invalid "
                    "signature, wrong issuer, and the refresh token flow."
                ),
            ),
            ("you", "Use vitest instead of jest"),
            ("kiro", "Switched — same test structure, just different imports and config."),
        ],
        20,
        15,
    ),
    (
        "Build a Slack bot for deployment notifications",
        "/Users/demo/projects/devops-tools",
        [
            (
                "you",
                (
                    "I want a Slack bot that posts deployment status to #releases, showing "
                    "who deployed, what changed, and the environment."
                ),
            ),
            (
                "kiro",
                (
                    "I'll create a Lambda triggered by CodePipeline events via EventBridge, "
                    "with a rich message including deployer, PR link, and status color coding."
                ),
            ),
        ],
        30,
        20,
    ),
    (
        "Debug memory leak in Node.js worker",
        "/Users/demo/projects/queue-processor",
        [
            ("you", "Our Node.js worker runs out of memory after about 6 hours."),
            (
                "kiro",
                (
                    "Let's find it with heap snapshots at intervals, then compare them "
                    "in Chrome DevTools to find growing objects."
                ),
            ),
            ("you", "Found it. We have an in-memory cache that never evicts entries."),
            ("kiro", "Classic leak. An LRU cache with a max size is the simplest fix here."),
        ],
        45,
        30,
    ),
    (
        "Create Terraform module for VPC with private subnets",
        "/Users/demo/projects/infra-modules",
        [
            (
                "you",
                (
                    "Create a reusable Terraform module for a VPC with public/private "
                    "subnets, NAT gateway, and VPC endpoints for S3 and DynamoDB."
                ),
            ),
            (
                "kiro",
                (
                    "I'll include 3 public + 3 private subnets across AZs, a configurable "
                    "NAT setup, gateway endpoints, flow logs, and cost allocation tags."
                ),
            ),
        ],
        60,
        40,
    ),
    (
        "Review pull request for payment service refactor",
        "/Users/demo/projects/payment-service",
        [
            ("you", "Review this PR that refactors payment processing to the Strategy pattern."),
            ("kiro", "Let me read through the changes."),
            ("kiro", "[tools: fs_read]"),
            (
                "kiro",
                (
                    "Solid refactor overall. Three concerns: a race condition in "
                    "processPayment(), a missing rollback path, and overly broad error "
                    "handling that should distinguish retryable from permanent failures."
                ),
            ),
        ],
        90,
        22,
    ),
]


def _now() -> datetime:
    """Return the current UTC time, as a single call site for easier testing."""
    return datetime.now(tz=timezone.utc)


def write_v3_session(
    root: Path,
    title: str,
    cwd: str,
    messages: list[tuple[str, str]],
    days_ago: int,
    duration_min: int,
    session_id: str | None = None,
) -> Path:
    """Write a CLI 3.0 session.json + messages.jsonl under root/<hash>/sess_<id>/.

    Returns the session directory.
    """
    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    now = _now()
    created = now - timedelta(days=days_ago, minutes=duration_min)
    updated = now - timedelta(days=days_ago)

    session_dir = root / "workspacehash" / sid
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session.json").write_text(
        json.dumps(
            {
                "id": sid,
                "title": title,
                "workspacePaths": [cwd],
                "createdAt": created.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lastModifiedAt": updated.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
        )
    )

    lines = []
    for role, text in messages:
        if text.startswith("[tools:"):
            lines.append({"payload": {"type": "tool_call", "toolName": text.strip("[]")}})
        else:
            lines.append(
                {"payload": {"type": "user" if role == "you" else "assistant", "content": text}}
            )
    lines.append(
        {
            "payload": {
                "type": "usage_summary",
                "promptTurnSummaries": [{"unit": "credit", "usage": round(duration_min * 0.05, 2)}],
            }
        }
    )
    (session_dir / "messages.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n"
    )
    return session_dir


def write_jsonl_session(
    root: Path,
    title: str,
    cwd: str,
    messages: list[tuple[str, str]],
    days_ago: int,
    duration_min: int,
    session_id: str | None = None,
) -> Path:
    """Write a CLI 2.x classic-mode <uuid>.json + <uuid>.jsonl under root.

    Returns the .json metadata file path.
    """
    sid = session_id or str(uuid.uuid4())
    now = _now()
    created = now - timedelta(days=days_ago, minutes=duration_min)
    updated = now - timedelta(days=days_ago)

    root.mkdir(parents=True, exist_ok=True)
    json_file = root / f"{sid}.json"
    json_file.write_text(
        json.dumps(
            {
                "session_id": sid,
                "title": title,
                "cwd": cwd,
                "created_at": created.strftime("%Y-%m-%dT%H:%M:%S"),
                "updated_at": updated.strftime("%Y-%m-%dT%H:%M:%S"),
                "session_state": {
                    "conversation_metadata": {
                        "user_turn_metadatas": [
                            {
                                "metering_usage": [
                                    {"value": round(duration_min * 0.05, 2), "unit": "credit"}
                                ]
                            }
                        ]
                    }
                },
            }
        )
    )

    jsonl_file = root / f"{sid}.jsonl"
    with jsonl_file.open("w") as f:
        for role, text in messages:
            if text.startswith("[tools:"):
                continue  # classic format has no dedicated tool-use line; skip
            kind = "Prompt" if role == "you" else "AssistantMessage"
            entry = {
                "version": "v1",
                "kind": kind,
                "data": {
                    "message_id": str(uuid.uuid4()),
                    "content": [{"kind": "text", "data": text}],
                },
            }
            f.write(json.dumps(entry) + "\n")
    return json_file


def write_sqlite_v2_sessions(
    db_path: Path,
    sessions: list[tuple[str, str, list[tuple[str, str]], int, int]],
) -> None:
    """Create (or append to) a data.sqlite3 database with conversations_v2 rows."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS conversations_v2 (
            key TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (key, conversation_id)
        )"""
    )

    now = _now()
    for title, cwd, messages, days_ago, duration_min in sessions:
        sid = str(uuid.uuid4())
        created = now - timedelta(days=days_ago, minutes=duration_min)
        updated = now - timedelta(days=days_ago)

        history = []
        for role, text in messages:
            entry: dict = {"user": {}, "assistant": {}}
            if role == "you":
                entry["user"] = {"content": {"Prompt": {"prompt": text}}}
            elif text.startswith("[tools:"):
                tool_name = text.strip("[]").split(": ", 1)[1]
                entry["assistant"] = {
                    "ToolUse": {
                        "message_id": str(uuid.uuid4()),
                        "content": "",
                        "tool_uses": [{"name": tool_name}],
                    }
                }
            else:
                entry["assistant"] = {
                    "Response": {"message_id": str(uuid.uuid4()), "content": text}
                }
            history.append(entry)

        # First message's prompt doubles as the title shown in the list, matching
        # how real v2 sessions (which have no separate title field) behave.
        value = json.dumps({"conversation_id": sid, "history": history})
        conn.execute(
            "INSERT OR REPLACE INTO conversations_v2 "
            "(key, conversation_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (cwd, sid, value, int(created.timestamp() * 1000), int(updated.timestamp() * 1000)),
        )
        del title  # title is derived from the first prompt for this format

    conn.commit()
    conn.close()

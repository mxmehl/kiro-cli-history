"""Generate synthetic Kiro CLI session data for demo recording.

Creates fake sessions in a temp directory that kiro-cli-history can read.
Run this, then launch kiro_history.py with KIRO_DEMO_MODE=1 to use the fake data.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DEMO_DIR = Path(__file__).parent / "demo_data"

# Synthetic sessions — realistic topics, no real data
SESSIONS = [
    {
        "title": "Deploy FastAPI app to ECS Fargate",
        "cwd": "/Users/demo/projects/weather-api",
        "messages": [
            ("you", "I have a FastAPI app that I want to deploy to ECS Fargate. Can you help me set up the infrastructure?"),
            ("kiro", "Sure! Let me look at your project structure first to understand what we're working with."),
            ("kiro", "[tools: fs_read]"),
            ("kiro", "I can see your FastAPI app with a Dockerfile. Let me create the ECS task definition, service, and ALB configuration.\n\nHere's the plan:\n1. Create an ECR repository\n2. Build and push the Docker image\n3. Create ECS cluster, task definition, and service\n4. Set up an ALB with health checks"),
            ("you", "Sounds good. Also add a CloudWatch dashboard for monitoring."),
            ("kiro", "I'll add CloudWatch alarms for CPU, memory, and 5xx errors. Let me create the CDK stack."),
            ("kiro", "[tools: fs_write]"),
            ("kiro", "Done! I've created `infra/ecs_stack.py` with the full setup. Run `cdk deploy` to provision everything. The dashboard will show:\n- Request count and latency\n- CPU and memory utilization\n- 5xx error rate with alarm at >1%"),
        ],
        "days_ago": 1,
        "duration_min": 25,
    },
    {
        "title": "Fix CORS issue in React + API Gateway",
        "cwd": "/Users/demo/projects/dashboard-frontend",
        "messages": [
            ("you", "My React app is getting CORS errors when calling my API Gateway endpoint. The preflight OPTIONS request is failing."),
            ("kiro", "This is a common issue with API Gateway. Let me check your API Gateway configuration."),
            ("kiro", "[tools: fs_read]"),
            ("kiro", "Found the issue. Your API Gateway is missing the CORS configuration for the OPTIONS preflight method. You need to:\n\n1. Enable CORS on the API Gateway resource\n2. Add the `Access-Control-Allow-Origin` header to your Lambda response\n3. Make sure your React app sends the correct `Content-Type`\n\nLet me fix all three."),
            ("you", "Why does it work in Postman but not in the browser?"),
            ("kiro", "Great question! Postman doesn't enforce CORS — it's a browser-only security mechanism. Browsers send a preflight OPTIONS request before the actual request to check if the server allows cross-origin requests. Postman skips this entirely, which is why it works there but fails in the browser."),
        ],
        "days_ago": 3,
        "duration_min": 12,
    },
    {
        "title": "Set up CI/CD pipeline with GitHub Actions",
        "cwd": "/Users/demo/projects/saas-platform",
        "messages": [
            ("you", "Help me create a GitHub Actions workflow for our Node.js monorepo. We need to run tests, build, and deploy to staging on PR merge."),
            ("kiro", "I'll create a workflow that handles your monorepo structure. Let me check what packages you have."),
            ("kiro", "[tools: code]"),
            ("kiro", "I see 4 packages: `api`, `web`, `shared`, and `worker`. I'll set up:\n\n1. **Path-based triggers** — only build packages that changed\n2. **Parallel test jobs** — each package runs independently\n3. **Staging deploy** — triggered on merge to main\n4. **Slack notification** — on success/failure"),
            ("you", "Can you add a preview deployment for each PR using Vercel?"),
            ("kiro", "Absolutely. I'll add a Vercel preview deployment step that comments the preview URL on the PR."),
        ],
        "days_ago": 5,
        "duration_min": 35,
    },
    {
        "title": "Analyze CloudWatch logs for Lambda timeout",
        "cwd": "/Users/demo/projects/data-pipeline",
        "messages": [
            ("you", "Our Lambda function is timing out intermittently. Can you help me figure out why?"),
            ("kiro", "Let me check the CloudWatch logs and the function configuration."),
            ("kiro", "[tools: code]"),
            ("kiro", "I found the issue. Your Lambda has a 30-second timeout but the DynamoDB query is doing a full table scan when the `status` field is missing from the event. This happens about 15% of the time based on the logs.\n\nThe fix is to add a GSI on the status field and validate the event input before querying."),
            ("you", "How much would the GSI cost?"),
            ("kiro", "For your current table size (~2GB, ~5M items), the GSI would cost approximately:\n- Storage: ~$0.50/month (mirrors the projected attributes)\n- Write capacity: ~$2.30/month (based on your current write pattern)\n- Read capacity: ~$0.80/month\n\nTotal: roughly **$3.60/month**. Much cheaper than the Lambda timeout retries you're paying for now."),
        ],
        "days_ago": 7,
        "duration_min": 18,
    },
    {
        "title": "Migrate PostgreSQL to Aurora Serverless v2",
        "cwd": "/Users/demo/projects/backend-services",
        "messages": [
            ("you", "We want to migrate our self-managed PostgreSQL on EC2 to Aurora Serverless v2. What's the best approach?"),
            ("kiro", "Good choice. Aurora Serverless v2 gives you auto-scaling without managing instances. Here's the migration path:\n\n1. **Create Aurora cluster** with PostgreSQL compatibility\n2. **Use DMS** for continuous replication from EC2 PostgreSQL\n3. **Validate data** with DMS validation tasks\n4. **Switch over** during a maintenance window\n\nThe key consideration is your PostgreSQL version — Aurora supports PG 13, 14, 15, and 16."),
            ("you", "We're on PostgreSQL 12. Is that a problem?"),
            ("kiro", "Yes, you'll need to upgrade first. PostgreSQL 12 reached end of life. I'd recommend:\n\n1. First upgrade to PG 15 on your EC2 instance using `pg_upgrade`\n2. Then migrate to Aurora\n\nThis way you handle the version upgrade and the platform migration as separate steps, reducing risk."),
            ("you", "What about the extensions we use? We have PostGIS, pg_cron, and pgvector."),
            ("kiro", "All three are supported on Aurora:\n- **PostGIS** — fully supported\n- **pg_cron** — supported since Aurora PG 12.6+\n- **pgvector** — supported since Aurora PG 15.4+\n\nSince you'll be on PG 15 after the upgrade, all your extensions will work. I'll create the migration plan with DMS task definitions."),
        ],
        "days_ago": 14,
        "duration_min": 42,
    },
    {
        "title": "Write unit tests for authentication middleware",
        "cwd": "/Users/demo/projects/auth-service",
        "messages": [
            ("you", "Help me write unit tests for our JWT authentication middleware in Express."),
            ("kiro", "Let me read the middleware code first."),
            ("kiro", "[tools: fs_read]"),
            ("kiro", "I'll write tests covering:\n1. Valid token — should call `next()`\n2. Missing token — should return 401\n3. Expired token — should return 401\n4. Invalid signature — should return 401\n5. Token with wrong issuer — should return 403\n6. Refresh token flow — should issue new access token"),
            ("you", "Use vitest instead of jest"),
            ("kiro", "Got it. Switching to vitest. The test structure stays the same, just different imports and config."),
        ],
        "days_ago": 20,
        "duration_min": 15,
    },
    {
        "title": "Build a Slack bot for deployment notifications",
        "cwd": "/Users/demo/projects/devops-tools",
        "messages": [
            ("you", "I want a Slack bot that posts deployment status to our #releases channel. It should show who deployed, what changed, and the environment."),
            ("kiro", "I'll create a Lambda function triggered by CodePipeline events via EventBridge. It'll format a rich Slack message with deployment details.\n\nThe message will include:\n- Deployer name (from git)\n- Commit message and PR link\n- Environment (staging/production)\n- Status with color coding (green/red)\n- Direct link to CloudWatch logs"),
        ],
        "days_ago": 30,
        "duration_min": 20,
    },
    {
        "title": "Debug memory leak in Node.js worker",
        "cwd": "/Users/demo/projects/queue-processor",
        "messages": [
            ("you", "Our Node.js worker process keeps running out of memory after about 6 hours. How do I find the memory leak?"),
            ("kiro", "Memory leaks in long-running Node.js processes are usually caused by event listeners, closures holding references, or unbounded caches. Let me help you diagnose this.\n\nFirst, add heap snapshots at intervals:\n```js\nconst v8 = require('v8');\nsetInterval(() => {\n  v8.writeHeapSnapshot();\n}, 3600000); // every hour\n```\n\nThen compare snapshots in Chrome DevTools to find growing objects."),
            ("you", "Found it. We have an in-memory cache that never evicts entries."),
            ("kiro", "Classic issue. You have a few options:\n1. **LRU cache** with a max size (use `lru-cache` package)\n2. **TTL-based expiry** — entries expire after N minutes\n3. **Move to Redis** — if the cache needs to be shared across workers\n\nFor a worker process, option 1 is usually best. Want me to implement it?"),
        ],
        "days_ago": 45,
        "duration_min": 30,
    },
    {
        "title": "Create Terraform module for VPC with private subnets",
        "cwd": "/Users/demo/projects/infra-modules",
        "messages": [
            ("you", "Create a reusable Terraform module for a VPC with public and private subnets, NAT gateway, and VPC endpoints for S3 and DynamoDB."),
            ("kiro", "I'll create a module with sensible defaults that can be customized per environment. The module will include:\n\n- VPC with configurable CIDR\n- 3 public + 3 private subnets across AZs\n- NAT Gateway (single or per-AZ, configurable)\n- S3 and DynamoDB gateway endpoints\n- Flow logs to CloudWatch\n- Tags for cost allocation"),
        ],
        "days_ago": 60,
        "duration_min": 40,
    },
    {
        "title": "Review pull request for payment service refactor",
        "cwd": "/Users/demo/projects/payment-service",
        "messages": [
            ("you", "Review this PR that refactors our payment processing to use the Strategy pattern. Check for edge cases."),
            ("kiro", "Let me read through the changes."),
            ("kiro", "[tools: fs_read]"),
            ("kiro", "Overall this is a solid refactor. A few concerns:\n\n1. **Race condition** in `processPayment()` — if two requests hit simultaneously, both could pass the idempotency check. Add a database-level unique constraint.\n2. **Missing rollback** — if the payment provider succeeds but your database write fails, you have an inconsistent state. Add a compensation transaction.\n3. **Error types** — you're catching all errors uniformly. Distinguish between retryable errors (network timeout) and permanent failures (invalid card)."),
        ],
        "days_ago": 90,
        "duration_min": 22,
    },
]


def generate_jsonl_sessions():
    """Generate fake v3 JSONL sessions."""
    sessions_dir = DEMO_DIR / "kiro" / "sessions" / "cli"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    for session in SESSIONS[:5]:  # First 5 as JSONL
        sid = str(uuid.uuid4())
        now = datetime.now()
        created = now - timedelta(days=session["days_ago"], minutes=session["duration_min"])
        updated = now - timedelta(days=session["days_ago"])

        # Write metadata JSON
        meta = {
            "session_id": sid,
            "cwd": session["cwd"],
            "created_at": created.isoformat() + "Z",
            "updated_at": updated.isoformat() + "Z",
            "title": session["title"],
            "session_state": {},
        }
        with open(sessions_dir / f"{sid}.json", "w") as f:
            json.dump(meta, f)

        # Write JSONL conversation
        with open(sessions_dir / f"{sid}.jsonl", "w") as f:
            for role, text in session["messages"]:
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


def generate_sqlite_sessions():
    """Generate fake v2 SQLite sessions."""
    db_dir = DEMO_DIR / "kiro-cli"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "data.sqlite3"

    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations_v2 (
        key TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        value TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY (key, conversation_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        key TEXT PRIMARY KEY, value TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS migrations (id INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS history (id INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state (id INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS auth_kv (id INTEGER)""")

    for session in SESSIONS[5:]:  # Remaining as SQLite v2
        sid = str(uuid.uuid4())
        now = datetime.now()
        created = now - timedelta(days=session["days_ago"], minutes=session["duration_min"])
        updated = now - timedelta(days=session["days_ago"])

        history = []
        for role, text in session["messages"]:
            entry = {"user": {}, "assistant": {}, "request_metadata": {}}
            if role == "you":
                entry["user"] = {
                    "additional_context": "",
                    "env_context": {},
                    "content": {"Prompt": {"prompt": text}},
                }
            else:
                if text.startswith("[tools:"):
                    entry["assistant"] = {"ToolUse": {
                        "message_id": str(uuid.uuid4()),
                        "content": "",
                        "tool_uses": [{"name": text.strip("[]").split(": ")[1]}],
                    }}
                else:
                    entry["assistant"] = {"Response": {
                        "message_id": str(uuid.uuid4()),
                        "content": text,
                    }}
            history.append(entry)

        value = json.dumps({
            "conversation_id": sid,
            "history": history,
            "next_message": None,
            "tools": {},
        })

        conn.execute(
            "INSERT INTO conversations_v2 (key, conversation_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session["cwd"], sid, value, int(created.timestamp() * 1000), int(updated.timestamp() * 1000)),
        )

    conn.commit()
    conn.close()


def main():
    if DEMO_DIR.exists():
        import shutil
        shutil.rmtree(DEMO_DIR)

    print("Generating synthetic demo data...")
    generate_jsonl_sessions()
    generate_sqlite_sessions()

    print(f"Demo data created in: {DEMO_DIR}")
    print(f"  JSONL sessions: {DEMO_DIR / 'kiro/sessions/cli/'}")
    print(f"  SQLite database: {DEMO_DIR / 'kiro-cli/data.sqlite3'}")
    print()
    print("To run with demo data:")
    print(f"  KIRO_DEMO_DIR={DEMO_DIR} python3 kiro_history.py")


if __name__ == "__main__":
    main()

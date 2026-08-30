"""Inject demo usage records so the Dashboard has data to show."""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.models.usage import UsageRecord
from app.models.organization import Organization
from app.models.user import User

DATABASE_URL = os.getenv(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://tokenguard:tokenguard_dev@localhost:5432/tokenguard",
)

# Demo data
MODELS = [
    ("claude-sonnet-4-20250514", "claude_code", "anthropic", 0.003),
    ("claude-opus-4-20250514", "claude_code", "anthropic", 0.015),
    ("o3-mini", "openai", "openai", 0.001),
    ("gpt-4.1", "openai", "openai", 0.002),
    ("gemini-2.5-pro", "gemini", "google", 0.001),
    ("deepseek-r1", "deepseek", "deepseek", 0.0005),
]

TOOLS = ["claude_code", "openai", "gemini", "deepseek", "cursor"]
USER_IDS = [uuid4() for _ in range(5)]


async def inject_demo():
    engine = create_async_engine(DATABASE_URL)
    sm = async_sessionmaker(engine)

    async with sm() as s:
        # Find or create a demo org
        result = await s.execute(text("SELECT id FROM organizations LIMIT 1"))
        row = result.first()
        if row:
            org_id = row[0]
        else:
            uid = uuid4()
            await s.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, plan, is_active, created_at) "
                    "VALUES (:id, 'Demo Org', 'demo', 'standard', true, :now)"
                ),
                {"id": uid, "now": datetime.now(timezone.utc)},
            )
            org_id = uid

        # Find or create a demo user
        result = await s.execute(text("SELECT id FROM users LIMIT 1"))
        row = result.first()
        if row:
            user_id = row[0]
        else:
            uid = uuid4()
            await s.execute(
                text(
                    "INSERT INTO users (id, email, name, password_hash, is_active, created_at, updated_at) "
                    "VALUES (:id, 'demo@example.com', 'Demo User', :pw, true, :now, :now)"
                ),
                {"id": uid, "pw": "$2b$12$LZmE4fDrWuCgbvU7IvMRWuRRoFJlqhiZnxVPBpycXJq4YOBSjJ1Ly"},
                {"now": datetime.now(timezone.utc)},
            )
            user_id = uid

        # Generate 30 days of usage data
        now = datetime.now(timezone.utc)
        records = []
        for day_offset in range(30):
            date = now - timedelta(days=day_offset)
            # 2-8 requests per day
            num_requests = 3 + (day_offset % 5)
            for i in range(num_requests):
                model_idx = (day_offset + i) % len(MODELS)
                model_id, tool, provider, cost_per_k = MODELS[model_idx]

                input_tokens = 2000 + (hash(f"{day_offset}-{i}-{model_id}") % 15000)
                output_tokens = 500 + (hash(f"{i}-{model_id}") % 5000)
                cost = Decimal(str(round((input_tokens + output_tokens) * cost_per_k / 1000 * 0.5 + 0.01, 4)))

                started = date.replace(
                    hour=8 + (i % 10),
                    minute=(i * 7) % 60,
                    second=(i * 13) % 60,
                    microsecond=0,
                )
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)

                records.append(UsageRecord(
                    organization_id=org_id,
                    user_id=user_id,
                    tool_name=tool,
                    model_name=model_id,
                    provider=provider,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=0,
                    cache_read_tokens=0,
                    cost_usd=cost,
                    task_type=["code_generation", "debugging", "refactoring", "documentation", "testing"][i % 5],
                    context_window_size=200000,
                    context_usage_pct=Decimal(str(round((input_tokens + output_tokens) / 200000, 4))),
                    started_at=started,
                    ended_at=started + timedelta(seconds=5 + i * 2),
                ))

        for rec in records:
            s.add(rec)

        await s.commit()
        print(f"Injected {len(records)} demo usage records for org {org_id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(inject_demo())

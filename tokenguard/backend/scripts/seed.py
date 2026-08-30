"""Seed model_pricing table."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

DATABASE_URL = os.getenv(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://tokenguard:tokenguard_dev@localhost:5432/tokenguard",
)

PRICING = [
    # (model_id, display_name, provider, input, output, cache_creation, cache_read, capability_level)
    # ── Anthropic (Claude) ──────────────────────────────────────────
    ("claude-sonnet-4-20250514", "Claude Sonnet 4", "anthropic", 3.0, 15.0, 0.30, 3.75, 3),
    ("claude-opus-4-20250514", "Claude Opus 4", "anthropic", 15.0, 75.0, 1.50, 18.75, 4),
    ("claude-haiku-4-20250514", "Claude Haiku 4", "anthropic", 0.8, 4.0, 0.08, 1.00, 1),
    ("claude-sonnet-4-5-20250514", "Claude Sonnet 4.5", "anthropic", 3.75, 15.0, 0.375, 3.75, 3),
    ("claude-opus-4-20250514-mini", "Claude Opus 4 Mini", "anthropic", 7.5, 37.5, 0.75, 9.375, 4),
    ("claude-fast-4-20250514", "Claude Fast 4", "anthropic", 1.5, 7.5, 0.15, 1.875, 2),
    # ── OpenAI ──────────────────────────────────────────────────────
    ("o4-mini", "o4 Mini", "openai", 1.1, 4.4, None, None, 4),
    ("o3", "o3", "openai", 10.0, 40.0, None, None, 4),
    ("o3-mini", "o3 Mini", "openai", 1.1, 4.4, None, None, 3),
    ("gpt-4.1", "GPT-4.1", "openai", 4.0, 16.0, None, None, 3),
    ("gpt-4.1-mini", "GPT-4.1 Mini", "openai", 0.4, 1.6, None, None, 2),
    ("gpt-4.1-nano", "GPT-4.1 Nano", "openai", 0.1, 0.4, None, None, 1),
    ("gpt-4.5-preview", "GPT-4.5 Preview", "openai", 7.5, 30.0, None, None, 4),
    ("chatgpt-4.5-api", "ChatGPT-4.5 API", "openai", 7.5, 30.0, None, None, 4),
    ("o1", "o1", "openai", 5.0, 25.0, None, None, 4),
    ("o1-pro", "o1 Pro", "openai", 15.0, 60.0, None, None, 4),
    # ── Google (Gemini) ─────────────────────────────────────────────
    ("gemini-2.5-pro", "Gemini 2.5 Pro", "google", 1.25, 15.0, 0.125, 0.15625, 4),
    ("gemini-2.5-flash", "Gemini 2.5 Flash", "google", 0.15, 1.0, 0.01875, 0.025, 3),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "google", 0.075, 0.3, 0.009375, 0.0125, 2),
    ("gemini-2.0-flash", "Gemini 2.0 Flash", "google", 0.15, 0.6, 0.01875, 0.025, 2),
    # ── DeepSeek ────────────────────────────────────────────────────
    ("deepseek-v3.2", "DeepSeek V3.2", "deepseek", 0.27, 1.1, None, None, 3),
    ("deepseek-r1", "DeepSeek R1", "deepseek", 0.55, 2.19, None, None, 4),
    ("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill Llama 70B", "deepseek", 0.12, 0.55, None, None, 3),
    ("deepseek-v3-lite", "DeepSeek V3 Lite", "deepseek", 0.07, 0.28, None, None, 1),
    # ── Meta ────────────────────────────────────────────────────────
    ("llama-4-scout", "Llama 4 Scout", "meta", 0.4, 2.0, None, None, 3),
    ("llama-4-maverick", "Llama 4 Maverick", "meta", 2.0, 10.0, None, None, 4),
    # ── Mistral ─────────────────────────────────────────────────────
    ("mistral-large-latest", "Mistral Large", "mistral", 2.0, 6.0, None, None, 3),
    ("ministral-3b-latest", "Ministral 3B", "mistral", 0.04, 0.04, None, None, 1),
    # ── AWS (Bedrock) ───────────────────────────────────────────────
    ("claude-sonnet-4-20250514-bedrock", "Claude Sonnet 4 (Bedrock)", "aws-bedrock", 3.0, 15.0, 0.30, 3.75, 3),
    ("claude-haiku-4-20250514-bedrock", "Claude Haiku 4 (Bedrock)", "aws-bedrock", 0.8, 4.0, 0.08, 1.00, 1),
    ("mistral-large-2-aws", "Mistral Large 2 (Bedrock)", "aws-bedrock", 2.0, 6.0, None, None, 3),
    # ── Azure OpenAI ────────────────────────────────────────────────
    ("gpt-4o-mini-azure", "GPT-4o Mini (Azure)", "azure", 0.15, 0.6, None, None, 1),
    ("gpt-4o-azure", "GPT-4o (Azure)", "azure", 1.5, 6.0, None, None, 3),
    ("o3-mini-azure", "o3 Mini (Azure)", "azure", 1.1, 4.4, None, None, 3),
]


async def seed():
    engine = create_async_engine(DATABASE_URL)
    sm = async_sessionmaker(engine)

    async with sm() as s:
        for row in PRICING:
            await s.execute(
                text(
                    "INSERT INTO model_pricing "
                    "(id, model_id, display_name, provider, input_price_per_million, "
                    "output_price_per_million, cache_creation_price_per_million, "
                    "cache_read_price_per_million, capability_level) "
                    "VALUES (gen_random_uuid(), :mid, :dn, :prov, :inp, :out, :cc, :cr, :cl) "
                    "ON CONFLICT (model_id) DO NOTHING"
                ),
                {
                    "mid": row[0], "dn": row[1], "prov": row[2],
                    "inp": row[3], "out": row[4], "cc": row[5],
                    "cr": row[6], "cl": row[7],
                },
            )
        await s.commit()

    print(f"Seeded {len(PRICING)} pricing rows.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

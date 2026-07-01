import os
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger("tokenguard.proxy")

# Token counts from Claude models
MODEL_TOKEN_RANGES = {
    "claude-sonnet-4-20250514": {"context_window": 200_000, "default_max": 8192},
    "claude-opus-4-20250514": {"context_window": 200_000, "default_max": 8192},
    "claude-haiku-4-20250514": {"context_window": 200_000, "default_max": 8192},
    "claude-3-5-sonnet-20241022": {"context_window": 200_000, "default_max": 8192},
    "claude-3-5-haiku-20241022": {"context_window": 200_000, "default_max": 8192},
    "claude-3-opus-20240229": {"context_window": 200_000, "default_max": 4096},
    "claude-3-sonnet-20240229": {"context_window": 200_000, "default_max": 4096},
}

# Pattern to detect file paths in messages (for Claude Code)
FILE_PATH_PATTERN = re.compile(r'[\'"]?(/[^\s\'"]*\.[\w]+)[\'"]?')


def get_model_info(model_name: str) -> dict:
    """Extract model metadata from model name."""
    # Normalize model aliases
    normalized = model_name
    if normalized.startswith("anthropic/"):
        normalized = normalized.split("/", 1)[1]

    info = MODEL_TOKEN_RANGES.get(normalized)
    if info is None:
        # Default conservative estimates
        info = {"context_window": 100_000, "default_max": 4096}

    return {
        "model_name": normalized,
        "context_window": info["context_window"],
        "default_max": info["default_max"],
    }


def estimate_input_tokens(messages: list[dict], system: list) -> int:
    """Rough token estimation from message content (~4 chars per token)."""
    content = ""
    for msg in messages:
        text = msg.get("content", "")
        if isinstance(text, str):
            content += text
        elif isinstance(text, list):
            for part in text:
                if isinstance(part, dict):
                    content += part.get("text", "")

    if isinstance(system, list):
        for item in system:
            text = item if isinstance(item, str) else item.get("text", "")
            content += text

    # Rough estimate: ~4 chars per token, plus overhead for tool results
    char_count = len(content.encode("utf-8"))
    token_estimate = max(1, char_count // 4)

    # Add overhead for message structure
    token_estimate += len(messages) * 5

    return token_estimate


def extract_project_name(messages: list[dict]) -> Optional[str]:
    """Try to extract project name from the first user message."""
    if not messages:
        return None
    first_msg = messages[0].get("content", "")
    if isinstance(first_msg, str):
        # Look for common project indicators
        for pattern in [r"project[:\s]+([^\n,]+)", r"repo[:\s]+([^\n,]+)"]:
            match = re.search(pattern, first_msg, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def should_trigger_warning(context_usage_pct: float) -> bool:
    """Check if context usage warrants a warning."""
    return context_usage_pct >= 0.9

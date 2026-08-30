"""Utility functions for token estimation, model info, and Project Attribution."""
import os
import re
import logging
from typing import Optional

from .pricing import get_context_window

logger = logging.getLogger("tokenguard.proxy")

# Known model defaults for max output tokens
MODEL_DEFAULT_MAX = {
    "claude-sonnet-4-20250514": 8192,
    "claude-opus-4-20250514": 8192,
    "claude-haiku-4-20250514": 8192,
    "claude-fast-4-20250514": 8192,
    "claude-sonnet-4-5-20250514": 8192,
    "claude-opus-4-20250514-mini": 8192,
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-5-haiku-20241022": 8192,
    "claude-3-opus-20240229": 4096,
    "claude-3-sonnet-20240229": 4096,
    "gpt-5.6-sol": 16384,
    "gpt-5.6-terra": 16384,
    "gpt-5.6-luna": 16384,
    "gpt-4.1": 16384,
    "gpt-4o": 16384,
    "gpt-4o-mini": 16384,
    "o3": 100000,
    "o3-mini": 100000,
    "o1": 100000,
    "deepseek-chat": 8192,
    "deepseek-r1": 8192,
    "deepseek-v3": 8192,
}

# Regex patterns for resolving project names from file paths and prompts
PROJECT_PATH_PATTERNS = [
    re.compile(r'/projects/([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'/workspaces?/([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'/repos?/([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'project[:\s=]+([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'repo[:\s=]+([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'/Volumes/[^/]+/projects/([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'/Users/[^/]+/projects/([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
    re.compile(r'[\'"]?(/[^\s\'"]+/([a-zA-Z0-9_\-\.]+)/(?:src|app|tests|tokenguard|frontend|backend)/)', re.IGNORECASE),
]


def get_model_info(model_name: str) -> dict:
    """Extract model metadata from model name."""
    normalized = model_name
    if normalized.startswith("anthropic/"):
        normalized = normalized.split("/", 1)[1]

    context_window = get_context_window(normalized)
    default_max = MODEL_DEFAULT_MAX.get(normalized, 4096)

    return {
        "model_name": normalized,
        "context_window": context_window,
        "default_max": default_max,
    }


def extract_project_name(messages: list = None, system = None, headers: dict = None) -> str:
    """Extract project/repository name from headers, message content, system prompts, or working directory.
    
    Falls back gracefully to 'General' if no specific project is identified.
    """
    # 1. Check explicit headers
    if headers:
        for hdr in ["x-project-name", "x-tokenguard-project", "x-repo-name"]:
            val = headers.get(hdr)
            if val and val.strip():
                return val.strip()

    # 2. Check text content in messages and system prompt
    text_corpus = ""
    if system:
        if isinstance(system, list):
            for item in system:
                text_corpus += (item if isinstance(item, str) else item.get("text", "")) + " "
        elif isinstance(system, str):
            text_corpus += system + " "

    if messages and isinstance(messages, list):
        for msg in messages[:5]:  # scan first few messages for project context
            content = msg.get("content", "")
            if isinstance(content, str):
                text_corpus += content + " "
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text_corpus += part.get("text", "") + " "

    # 3. Match against project regex patterns
    if text_corpus:
        for pattern in PROJECT_PATH_PATTERNS:
            match = pattern.search(text_corpus)
            if match:
                name = match.group(1).strip().strip("/'\"")
                if name and len(name) > 1 and not name.startswith("."):
                    return name

    # 4. Fallback to default
    return "General"


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

    char_count = len(content.encode("utf-8"))
    token_estimate = max(1, char_count // 4)
    token_estimate += len(messages) * 5
    return token_estimate


def should_trigger_warning(context_usage_pct: float) -> bool:
    """Check if context usage warrants a warning (>90%)."""
    return context_usage_pct >= 0.9

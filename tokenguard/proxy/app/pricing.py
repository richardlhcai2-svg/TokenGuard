"""Per-provider model pricing and context lookup. Official 2025/2026 API rates."""
import re
from typing import Optional, Dict, Any

# Universal Model Catalog: Pricing per 1K tokens ($/1K) & Context Windows
# Formula: $X / 1,000,000 tokens -> $X / 1,000 per 1K tokens
CATALOG: Dict[str, Dict[str, Any]] = {
    # ----------------------------------------------------
    # 1. Anthropic Claude Family (Official API Rates)
    # ----------------------------------------------------
    # Claude Opus ($15.00 / 1M in, $75.00 / 1M out, $1.50 / 1M cache read)
    "claude-opus-5": {"input_per_k": 0.0050, "output_per_k": 0.0250, "cache_read_per_k": 0.0005, "context": 200000},
    "claude-fable-5": {"input_per_k": 0.0100, "output_per_k": 0.0500, "cache_read_per_k": 0.0010, "context": 200000},
    "claude-opus-4-8": {"input_per_k": 0.0150, "output_per_k": 0.0750, "cache_read_per_k": 0.0015, "context": 200000},
    "claude-opus-4": {"input_per_k": 0.0150, "output_per_k": 0.0750, "cache_read_per_k": 0.0015, "context": 200000},
    "claude-3-opus": {"input_per_k": 0.0150, "output_per_k": 0.0750, "cache_read_per_k": 0.0015, "context": 200000},
    
    # Claude Sonnet ($3.00 / 1M in, $15.00 / 1M out, $0.30 / 1M cache read)
    "claude-sonnet-5": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-sonnet-4-6": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-sonnet-4-5": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-sonnet-4": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-3-7-sonnet": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-3.7-sonnet": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-3-5-sonnet": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-3.5-sonnet": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},
    "claude-fast-4": {"input_per_k": 0.0015, "output_per_k": 0.0075, "cache_read_per_k": 0.00015, "context": 200000},
    
    # Claude Haiku ($0.80 / 1M in, $4.00 / 1M out, $0.08 / 1M cache read)
    "claude-haiku-4-5": {"input_per_k": 0.0008, "output_per_k": 0.0040, "cache_read_per_k": 0.00008, "context": 200000},
    "claude-haiku-4": {"input_per_k": 0.0008, "output_per_k": 0.0040, "cache_read_per_k": 0.00008, "context": 200000},
    "claude-3-5-haiku": {"input_per_k": 0.0008, "output_per_k": 0.0040, "cache_read_per_k": 0.00008, "context": 200000},
    "claude-3-haiku": {"input_per_k": 0.00025, "output_per_k": 0.00125, "cache_read_per_k": 0.000025, "context": 200000},
    "claude-": {"input_per_k": 0.0030, "output_per_k": 0.0150, "cache_read_per_k": 0.0003, "context": 200000},

    # ----------------------------------------------------
    # 2. Google Gemini Family (Official API Rates)
    # ----------------------------------------------------
    # Gemini Flash Series ($0.10 / 1M in = 0.00010/1K, $0.40 / 1M out = 0.00040/1K)
    "gemini-3.7-flash": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "gemini-3.7": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "gemini-2.5-flash": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "gemini-2.0-flash-lite": {"input_per_k": 0.000075, "output_per_k": 0.00030, "cache_read_per_k": 0.000018, "context": 1048576},
    "gemini-2.0-flash": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "gemini-2.0": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "gemini-1.5-flash": {"input_per_k": 0.000075, "output_per_k": 0.00030, "cache_read_per_k": 0.000018, "context": 1048576},
    "agnes-2.5-flash": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "agnes-2.0-flash": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},
    "agnes-": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},

    # Gemini Pro Series ($1.25 / 1M in = 0.00125/1K, $5.00 / 1M out = 0.00500/1K)
    "gemini-3.1-pro": {"input_per_k": 0.00125, "output_per_k": 0.00500, "cache_read_per_k": 0.0003125, "context": 1048576},
    "gemini-3-pro": {"input_per_k": 0.00125, "output_per_k": 0.00500, "cache_read_per_k": 0.0003125, "context": 1048576},
    "gemini-2.5-pro": {"input_per_k": 0.00125, "output_per_k": 0.00500, "cache_read_per_k": 0.0003125, "context": 1048576},
    "gemini-1.5-pro": {"input_per_k": 0.00125, "output_per_k": 0.00500, "cache_read_per_k": 0.0003125, "context": 2097152},
    "gemini-": {"input_per_k": 0.00010, "output_per_k": 0.00040, "cache_read_per_k": 0.000025, "context": 1048576},

    # ----------------------------------------------------
    # 3. DeepSeek Family (Official API Rates)
    # ----------------------------------------------------
    # DeepSeek-V3 / Chat / V4 Flash ($0.27 / 1M miss, $0.07 / 1M hit, $1.10 / 1M out)
    "deepseek-v4-flash": {"input_per_k": 0.00027, "output_per_k": 0.00110, "cache_read_per_k": 0.00007, "context": 128000},
    "deepseek-v3": {"input_per_k": 0.00027, "output_per_k": 0.00110, "cache_read_per_k": 0.00007, "context": 128000},
    "deepseek-chat": {"input_per_k": 0.00027, "output_per_k": 0.00110, "cache_read_per_k": 0.00007, "context": 128000},
    
    # DeepSeek-R1 / V4 Pro Reasoner ($0.55 / 1M miss, $0.14 / 1M hit, $2.19 / 1M out)
    "deepseek-r1": {"input_per_k": 0.00055, "output_per_k": 0.00219, "cache_read_per_k": 0.00014, "context": 128000},
    "deepseek-v4-pro": {"input_per_k": 0.00055, "output_per_k": 0.00219, "cache_read_per_k": 0.00014, "context": 128000},
    "deepseek-reasoner": {"input_per_k": 0.00055, "output_per_k": 0.00219, "cache_read_per_k": 0.00014, "context": 128000},
    "deepseek-coder": {"input_per_k": 0.00014, "output_per_k": 0.00028, "cache_read_per_k": 0.00004, "context": 128000},
    "deepseek-": {"input_per_k": 0.00027, "output_per_k": 0.00110, "cache_read_per_k": 0.00007, "context": 128000},

    # ----------------------------------------------------
    # 4. Groq Ultra-Fast Inference Cloud (Official API Rates)
    # ----------------------------------------------------
    "llama-3.3-70b-versatile": {"input_per_k": 0.00059, "output_per_k": 0.00079, "cache_read_per_k": 0.00030, "context": 128000},
    "llama-3.3-70b": {"input_per_k": 0.00059, "output_per_k": 0.00079, "cache_read_per_k": 0.00030, "context": 128000},
    "llama-3.1-70b-versatile": {"input_per_k": 0.00059, "output_per_k": 0.00079, "cache_read_per_k": 0.00030, "context": 128000},
    "llama-3.1-8b-instant": {"input_per_k": 0.00005, "output_per_k": 0.00008, "cache_read_per_k": 0.000025, "context": 128000},
    "llama-3.1-8b": {"input_per_k": 0.00005, "output_per_k": 0.00008, "cache_read_per_k": 0.000025, "context": 128000},
    "llama3-70b-8192": {"input_per_k": 0.00059, "output_per_k": 0.00079, "cache_read_per_k": 0.00030, "context": 8192},
    "llama3-8b-8192": {"input_per_k": 0.00005, "output_per_k": 0.00008, "cache_read_per_k": 0.000025, "context": 8192},
    "mixtral-8x7b-32768": {"input_per_k": 0.00024, "output_per_k": 0.00024, "cache_read_per_k": 0.00012, "context": 32768},
    "gemma2-9b-it": {"input_per_k": 0.00020, "output_per_k": 0.00020, "cache_read_per_k": 0.00010, "context": 8192},
    "gemma-7b-it": {"input_per_k": 0.00007, "output_per_k": 0.00007, "cache_read_per_k": 0.00004, "context": 8192},
    "deepseek-r1-distill-llama-70b": {"input_per_k": 0.00075, "output_per_k": 0.00099, "cache_read_per_k": 0.00037, "context": 128000},
    "deepseek-r1-distill-qwen-32b": {"input_per_k": 0.00050, "output_per_k": 0.00075, "cache_read_per_k": 0.00025, "context": 128000},
    "qwen-2.5-coder-32b": {"input_per_k": 0.00050, "output_per_k": 0.00075, "cache_read_per_k": 0.00025, "context": 128000},
    "qwen-2.5-32b": {"input_per_k": 0.00050, "output_per_k": 0.00075, "cache_read_per_k": 0.00025, "context": 128000},

    # ----------------------------------------------------
    # 5. Moonshot AI / Kimi (Official API Rates)
    # ----------------------------------------------------
    "kimi-k3-free": {"input_per_k": 0.0000, "output_per_k": 0.0000, "cache_read_per_k": 0.0000, "context": 200000},
    "kimi-k3": {"input_per_k": 0.00050, "output_per_k": 0.00150, "cache_read_per_k": 0.00015, "context": 200000},
    "kimi-latest": {"input_per_k": 0.00050, "output_per_k": 0.00150, "cache_read_per_k": 0.00015, "context": 200000},
    "moonshot-v1-8k": {"input_per_k": 0.0120, "output_per_k": 0.0120, "cache_read_per_k": 0.0030, "context": 8192},
    "moonshot-v1-32k": {"input_per_k": 0.0240, "output_per_k": 0.0240, "cache_read_per_k": 0.0060, "context": 32768},
    "moonshot-v1-128k": {"input_per_k": 0.0600, "output_per_k": 0.0600, "cache_read_per_k": 0.0150, "context": 128000},
    "moonshot-v1-auto": {"input_per_k": 0.0120, "output_per_k": 0.0120, "cache_read_per_k": 0.0030, "context": 128000},
    "moonshot-": {"input_per_k": 0.0120, "output_per_k": 0.0120, "cache_read_per_k": 0.0030, "context": 128000},
    "kimi-": {"input_per_k": 0.00050, "output_per_k": 0.00150, "cache_read_per_k": 0.00015, "context": 200000},

    # ----------------------------------------------------
    # 6. Zhipu AI / 智谱 GLM 系列 (Official API Rates)
    # ----------------------------------------------------
    "glm-5.2": {"input_per_k": 0.00080, "output_per_k": 0.00160, "cache_read_per_k": 0.00040, "context": 128000},
    "glm-5": {"input_per_k": 0.00080, "output_per_k": 0.00160, "cache_read_per_k": 0.00040, "context": 128000},
    "glm-4-plus": {"input_per_k": 0.00080, "output_per_k": 0.00160, "cache_read_per_k": 0.00040, "context": 128000},
    "glm-4-0520": {"input_per_k": 0.00080, "output_per_k": 0.00160, "cache_read_per_k": 0.00040, "context": 128000},
    "glm-4-air": {"input_per_k": 0.00010, "output_per_k": 0.00010, "cache_read_per_k": 0.00005, "context": 128000},
    "glm-4-airx": {"input_per_k": 0.00020, "output_per_k": 0.00020, "cache_read_per_k": 0.00010, "context": 8192},
    "glm-4-flash": {"input_per_k": 0.00000, "output_per_k": 0.00000, "cache_read_per_k": 0.00000, "context": 128000},
    "glm-4-flashx": {"input_per_k": 0.00001, "output_per_k": 0.00001, "cache_read_per_k": 0.000005, "context": 128000},
    "glm-4-long": {"input_per_k": 0.00010, "output_per_k": 0.00010, "cache_read_per_k": 0.00005, "context": 1000000},
    "glm-zero-preview": {"input_per_k": 0.00050, "output_per_k": 0.00150, "cache_read_per_k": 0.00025, "context": 128000},
    "glm-reasoner": {"input_per_k": 0.00050, "output_per_k": 0.00150, "cache_read_per_k": 0.00025, "context": 128000},
    "codegeex-4": {"input_per_k": 0.00001, "output_per_k": 0.00001, "cache_read_per_k": 0.000005, "context": 128000},
    "glm-": {"input_per_k": 0.00080, "output_per_k": 0.00160, "cache_read_per_k": 0.00040, "context": 128000},

    # ----------------------------------------------------
    # 7. Alibaba Cloud / Qwen 系列 (DashScope / SiliconFlow)
    # ----------------------------------------------------
    "qwen-2.5-72b-instruct": {"input_per_k": 0.00035, "output_per_k": 0.00070, "cache_read_per_k": 0.00017, "context": 128000},
    "qwen-2.5-72b": {"input_per_k": 0.00035, "output_per_k": 0.00070, "cache_read_per_k": 0.00017, "context": 128000},
    "qwen-2.5-coder-32b-instruct": {"input_per_k": 0.00020, "output_per_k": 0.00040, "cache_read_per_k": 0.00010, "context": 128000},
    "qwen-2.5-coder-7b-instruct": {"input_per_k": 0.00005, "output_per_k": 0.00010, "cache_read_per_k": 0.000025, "context": 128000},
    "qwen-2.5-coder-7b": {"input_per_k": 0.00005, "output_per_k": 0.00010, "cache_read_per_k": 0.000025, "context": 128000},
    "qwen-max": {"input_per_k": 0.00160, "output_per_k": 0.00640, "cache_read_per_k": 0.00040, "context": 32768},
    "qwen-plus": {"input_per_k": 0.00040, "output_per_k": 0.00120, "cache_read_per_k": 0.00010, "context": 128000},
    "qwen-turbo": {"input_per_k": 0.00005, "output_per_k": 0.00015, "cache_read_per_k": 0.000015, "context": 128000},
    "qwq-32b-preview": {"input_per_k": 0.00040, "output_per_k": 0.00120, "cache_read_per_k": 0.00010, "context": 128000},
    "qwq-": {"input_per_k": 0.00040, "output_per_k": 0.00120, "cache_read_per_k": 0.00010, "context": 128000},
    "qwen-": {"input_per_k": 0.00035, "output_per_k": 0.00070, "cache_read_per_k": 0.00017, "context": 128000},

    # ----------------------------------------------------
    # 8. OpenAI & Codex Family (Official API Rates)
    # ----------------------------------------------------
    # GPT-5.6 Sol / Terra / Luna (Codex)
    "gpt-5.6-sol": {"input_per_k": 0.0050, "output_per_k": 0.0150, "cache_read_per_k": 0.0025, "context": 1000000},
    "gpt-5.6-terra": {"input_per_k": 0.0025, "output_per_k": 0.0100, "cache_read_per_k": 0.00125, "context": 500000},
    "gpt-5.6-luna": {"input_per_k": 0.0010, "output_per_k": 0.0040, "cache_read_per_k": 0.0005, "context": 250000},
    "sol": {"input_per_k": 0.0050, "output_per_k": 0.0150, "cache_read_per_k": 0.0025, "context": 1000000},
    "terra": {"input_per_k": 0.0025, "output_per_k": 0.0100, "cache_read_per_k": 0.00125, "context": 500000},
    "luna": {"input_per_k": 0.0010, "output_per_k": 0.0040, "cache_read_per_k": 0.0005, "context": 250000},
    
    # OpenAI o1 / o3 / o4 Reasoning Series
    "o4-mini": {"input_per_k": 0.0011, "output_per_k": 0.0044, "cache_read_per_k": 0.00055, "context": 200000},
    "o4": {"input_per_k": 0.0100, "output_per_k": 0.0400, "cache_read_per_k": 0.0050, "context": 200000},
    "o3-mini": {"input_per_k": 0.0011, "output_per_k": 0.0044, "cache_read_per_k": 0.00055, "context": 200000},
    "o3": {"input_per_k": 0.0100, "output_per_k": 0.0400, "cache_read_per_k": 0.0050, "context": 200000},
    "o1-mini": {"input_per_k": 0.0011, "output_per_k": 0.0044, "cache_read_per_k": 0.00055, "context": 200000},
    "o1-preview": {"input_per_k": 0.0150, "output_per_k": 0.0600, "cache_read_per_k": 0.0075, "context": 200000},
    "o1-pro": {"input_per_k": 0.0150, "output_per_k": 0.0600, "cache_read_per_k": 0.0075, "context": 200000},
    "o1": {"input_per_k": 0.0150, "output_per_k": 0.0600, "cache_read_per_k": 0.0075, "context": 200000},

    # Standard GPT-4o / GPT-4.5
    "gpt-4.5": {"input_per_k": 0.0075, "output_per_k": 0.0300, "cache_read_per_k": 0.00375, "context": 128000},
    "gpt-4.1-mini": {"input_per_k": 0.0004, "output_per_k": 0.0016, "cache_read_per_k": 0.0002, "context": 128000},
    "gpt-4.1-nano": {"input_per_k": 0.0001, "output_per_k": 0.0004, "cache_read_per_k": 0.00005, "context": 128000},
    "gpt-4.1": {"input_per_k": 0.0040, "output_per_k": 0.0160, "cache_read_per_k": 0.0020, "context": 2000000},
    "gpt-4o-mini": {"input_per_k": 0.00015, "output_per_k": 0.00060, "cache_read_per_k": 0.000075, "context": 128000},
    "gpt-4o": {"input_per_k": 0.00250, "output_per_k": 0.01000, "cache_read_per_k": 0.00125, "context": 128000},
    "gpt-4-turbo": {"input_per_k": 0.01000, "output_per_k": 0.03000, "cache_read_per_k": 0.00500, "context": 128000},
    "gpt-4": {"input_per_k": 0.03000, "output_per_k": 0.06000, "cache_read_per_k": 0.01500, "context": 8192},
    "gpt-3.5-turbo": {"input_per_k": 0.00150, "output_per_k": 0.00200, "cache_read_per_k": 0.00075, "context": 16385},
    "gpt-oss-120b": {"input_per_k": 0.00060, "output_per_k": 0.00180, "cache_read_per_k": 0.00030, "context": 128000},

    # ----------------------------------------------------
    # 9. Meta Llama, Mistral & Partner Models
    # ----------------------------------------------------
    "llama-3.1-70b": {"input_per_k": 0.00050, "output_per_k": 0.00080, "cache_read_per_k": 0.00025, "context": 128000},
    "llama-3.3-70b": {"input_per_k": 0.00050, "output_per_k": 0.00080, "cache_read_per_k": 0.00025, "context": 128000},
    "llama-3.1-405b": {"input_per_k": 0.00200, "output_per_k": 0.00400, "cache_read_per_k": 0.00100, "context": 128000},
    "llama-3.1-8b": {"input_per_k": 0.00005, "output_per_k": 0.00008, "cache_read_per_k": 0.000025, "context": 128000},
    "llama-": {"input_per_k": 0.00050, "output_per_k": 0.00080, "cache_read_per_k": 0.00025, "context": 128000},

    "codestral-22b": {"input_per_k": 0.00020, "output_per_k": 0.00060, "cache_read_per_k": 0.00010, "context": 32768},
    "codestral": {"input_per_k": 0.00020, "output_per_k": 0.00060, "cache_read_per_k": 0.00010, "context": 32768},
    "mistral-large": {"input_per_k": 0.00200, "output_per_k": 0.00600, "cache_read_per_k": 0.00100, "context": 128000},
    "mistral-": {"input_per_k": 0.00020, "output_per_k": 0.00060, "cache_read_per_k": 0.00010, "context": 32768},

    "step-3.5-flash": {"input_per_k": 0.00015, "output_per_k": 0.00060, "cache_read_per_k": 0.00004, "context": 128000},
    "step-": {"input_per_k": 0.00015, "output_per_k": 0.00060, "cache_read_per_k": 0.00004, "context": 128000},

    "nemotron-3-super-120b": {"input_per_k": 0.00060, "output_per_k": 0.00180, "cache_read_per_k": 0.00030, "context": 128000},
    "nemotron-": {"input_per_k": 0.00060, "output_per_k": 0.00180, "cache_read_per_k": 0.00030, "context": 128000},

    # Global Fallbacks
    "auto/best-coding": {"input_per_k": 0.00300, "output_per_k": 0.01500, "cache_read_per_k": 0.00030, "context": 200000},
    "<synthetic>": {"input_per_k": 0.00000, "output_per_k": 0.00000, "cache_read_per_k": 0.00000, "context": 100000},
    "__default__": {"input_per_k": 0.00200, "output_per_k": 0.00800, "cache_read_per_k": 0.00030, "context": 128000},
}

PROVIDER_COST_MAP = {
    "anthropic": {k: v for k, v in CATALOG.items() if k.startswith("claude") or k.startswith("agnes")},
    "openai": {k: v for k, v in CATALOG.items() if k.startswith("gpt") or k.startswith("o1") or k.startswith("o3") or k.startswith("o4") or k in ["sol", "terra", "luna"]},
    "gemini": {k: v for k, v in CATALOG.items() if k.startswith("gemini")},
    "deepseek": {k: v for k, v in CATALOG.items() if k.startswith("deepseek")},
    "groq": {k: v for k, v in CATALOG.items() if "groq" in k or k.startswith("llama") or k.startswith("mixtral") or k.startswith("gemma")},
    "kimi": {k: v for k, v in CATALOG.items() if k.startswith("kimi") or k.startswith("moonshot")},
    "zhipu": {k: v for k, v in CATALOG.items() if k.startswith("glm") or k.startswith("codegeex")},
    "qwen": {k: v for k, v in CATALOG.items() if k.startswith("qwen") or k.startswith("qwq")},
}

MODEL_CONTEXTS = {k: v.get("context", 128000) for k, v in CATALOG.items()}


def normalize_model_name(raw: str) -> str:
    """Normalize model string by removing tool annotations and routing prefixes."""
    if not raw:
        return ""
    name = raw.strip()
    # Strip parentheses e.g. (Antigravity), (ChatGPT Codex)
    if "(" in name:
        name = name.split("(")[0].strip()
    # Strip router/org prefixes e.g. gemini/..., deepseek-ai/..., amd/..., tokenrouter/moonshotai/...
    if "/" in name:
        parts = name.split("/")
        name = parts[-1]
    return name.lower()


def get_model_cost(model_name: str, provider: Optional[str] = None) -> Dict[str, float]:
    """Get cost per 1K tokens for a model. Universal longest prefix match."""
    clean = normalize_model_name(model_name)
    if clean in CATALOG:
        return CATALOG[clean]
    
    matches = [(k, v) for k, v in CATALOG.items() if k != "__default__" and clean.startswith(k)]
    if matches:
        return max(matches, key=lambda x: len(x[0]))[1]
    
    # Provider-based fallback if available
    if provider:
        p = provider.lower()
        if "anthropic" in p or "claude" in p:
            return CATALOG["claude-"]
        if "gemini" in p or "google" in p:
            return CATALOG["gemini-"]
        if "deepseek" in p:
            return CATALOG["deepseek-"]
        if "groq" in p:
            return CATALOG.get("llama-3.3-70b-versatile", CATALOG["__default__"])
        if "kimi" in p or "moonshot" in p:
            return CATALOG.get("kimi-k3", CATALOG["__default__"])
        if "zhipu" in p or "glm" in p:
            return CATALOG.get("glm-4-plus", CATALOG["__default__"])
        if "qwen" in p:
            return CATALOG.get("qwen-2.5-72b-instruct", CATALOG["__default__"])
        if "openai" in p:
            return CATALOG["gpt-4o"]
            
    return CATALOG["__default__"]


def get_context_window(model_name: str) -> int:
    """Get context window size for a model. Universal longest prefix match."""
    clean = normalize_model_name(model_name)
    if clean in CATALOG:
        return CATALOG[clean].get("context", 128000)
        
    matches = [(k, v) for k, v in CATALOG.items() if k != "__default__" and clean.startswith(k)]
    if matches:
        return max(matches, key=lambda x: len(x[0]))[1].get("context", 128000)
        
    return 100000

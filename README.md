# 🛡️ TokenGuard

<p align="center">
  <b>Industrial-Grade AI Cost Intelligence, Context Window HUD & Telemetry Proxy for Modern AI Coding Workflows</b>
</p>

<p align="center">
  <a href="https://pypi.org/project/tokenguard/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="MIT License"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/Architecture-Fail--Open%20%7C%20Non--Blocking-00C853.svg?style=flat" alt="Fail Open"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/Memory%20Footprint-%3C50MB%20Constant-6366F1.svg?style=flat" alt="Low Memory"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/Idle%20CPU-0.0%25-brightgreen.svg?style=flat" alt="Zero CPU"></a>
</p>

<p align="center">
  [ <b>English</b> ] · [ <a href="README.zh-CN.md">简体中文</a> ]
</p>

---

## 💡 What is TokenGuard?

When using autonomous coding agents and LLM tools like **Claude Code**, **Antigravity (Gemini)**, **ChatGPT / Codex**, and **DeepSeek**, software engineers face critical operational hurdles:

1. **Unclear Cost Attribution**: Monthly bills arrive as an aggregated black box. You cannot see how much budget was consumed by specific Git repositories, client deliverables, or background tasks.
2. **Silent Context Window Blowouts**: Multi-turn sessions silently swell beyond 100k+ tokens, degrading reasoning quality and triggering costly auto-compacting and runaway token burn.
3. **Proxy Instability & Connection Resets**: Traditional local proxies accumulate huge SSE streaming buffers or lock local databases, causing `ECONNRESET`, dropped network connections, and IDE freezes during intense coding tasks.

**TokenGuard** solves these problems through an **OmniRoute-inspired, zero-blocking, high-availability local proxy architecture**. It captures live token metrics in $O(1)$ constant memory, calculates exact costs with prompt caching discounts, and delivers a **taste-engineered dark OLED dashboard** featuring a dedicated **4-Tool Matrix Cockpit**.

```bash
pip install tokenguard
tg serve
```

---

## ⚡ Key Highlights & Architecture

### 1. 🛡️ 100% Fail-Open & Zero-Blocking Data Plane
- **Isolated Forwarding Pipeline**: Upstream LLM proxy forwarding is strictly decoupled from storage and analytics. 
- **Non-Blocking Ring Buffer**: Uses an asynchronous bounded queue (`maxsize=2000`) with a *Drop-Oldest* eviction policy. Even during database file locks or high concurrency spikes, your coding tools will **never experience an `ECONNRESET` or latency hit**.
- **$O(1)$ Stream Sniffer**: Reads and forwards SSE response chunks on the fly with zero string accumulation in memory.

### 2. 🎛️ Dedicated 4-Tool Matrix Cockpit
Real-time operational telemetry, live context window pressure (0–100%+), peak usage dials, and actionable optimization prompts for top developer tools:
- 🟣 **Claude Code CLI** (Anthropic Sonnet 3.7 / 3.5, Opus 3/4)
- 🟢 **Antigravity** (Google DeepMind Gemini 3.7 Pro / 2.5 Flash)
- 🔵 **ChatGPT / Codex** (OpenAI GPT-5.6 Sol / GPT-4o / o3-mini)
- 🟡 **DeepSeek** (DeepSeek-V4-Flash / R1 / V4-Pro)

### 3. 📁 Lifetime Git Project & Workspace Attribution
- Automatically attributes token usage to active Git repositories (e.g. `my-web-app`, `ai-agent`, `data-pipeline`, `tokenguard`).
- Track lifetime expenditures, token throughput, and invocation frequency per project.

### 4. 🎨 Taste-Engineered Visual HUD Dashboard
- **Dark OLED Glassmorphism**: Designed with Linear, Raycast, and Vercel aesthetic sensibilities.
- **Dynamic Expenditure & Trajectory Area Chart**: Responsive SVG visualization with hover tooltips and daily breakdowns.
- **Top Models Leaderboard & Stream Telemetry**: Real-time request stream with token flow ratios (`140k → 1.2k`) and cost tags.
- **Bilingual Interface**: Seamless one-click English / 简体中文 (`中 / EN`) switching.
- **Flexible Timeframes**: Switch between `Today (24h)`, `Last 7 Days`, `Last 30 Days`, and `All-Time Cumulative`.

### 5. 🪶 Ultra-Low System Footprint
- **Constant Memory**: `< 50MB RAM` regardless of streaming payload sizes.
- **Zero Idle CPU Drain**: `0.0% CPU` when no requests are in transit.
- **Local-First & Private**: All data is stored in local SQLite WAL (`~/.tokenguard/usage.db`). Zero telemetry leaves your machine.

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install tokenguard
```

### 2. Launch Proxy Daemon
```bash
tg serve
```
TokenGuard starts the local proxy on `http://localhost:8001` and serves the web dashboard at `http://localhost:8001/dashboard`.

*(Optional: Run as a background macOS LaunchAgent via `tg serve --daemon`)*

### 3. Configure Your AI Coding Tools

#### A. Claude Code CLI
Set the proxy endpoint in your environment or shell configuration:
```bash
export ANTHROPIC_BASE_URL="http://localhost:8001"
```

#### B. Antigravity (Gemini API)
```bash
export GEMINI_BASE_URL="http://localhost:8001"
```

#### C. OpenAI / Codex / ChatGPT CLI
```bash
export OPENAI_BASE_URL="http://localhost:8001/v1"
```

#### D. Multi-Model Relays (fcc-server / OmniRoute)
Route upstream traffic through `http://localhost:8001` with optional TokenGuard authentication headers:
```http
x-tokenguard-key: <your-proxy-secret>
```

---

## 💻 CLI Commands Reference

| Command | Description |
|---|---|
| `tg serve` | Start the non-blocking proxy daemon and web dashboard on port 8001 |
| `tg dashboard` | Launch the web dashboard in your default browser |
| `tg stats` | Print token usage and cost breakdown in terminal |
| `tg stats --watch` | Live-updating terminal HUD with 1-second refresh rate |
| `tg projects` | Show all-time Project & Workspace Cost Attribution table |
| `tg config` | Inspect and configure local API keys and proxy settings |
| `tg quickstart` | Interactive setup wizard for first-time onboarding |
| `tg --help` | View all available flags and options |

---

## 📁 Project Cost Attribution in Action

```text
╭────────────── 📁 Project Cost Attribution (All-Time Lifetime) ───────────────╮
│                📁 AI Cost Attribution by Project / Workspace                 │
│  Project /                                                                   │
│  Workspace             Spent  Share         Tokens  Calls  Last Active       │
│  📁 my-web-app        $18.50  38.1%     35,240,100    420  2026-09-04 15:05  │
│  📁 ai-agent          $14.20  29.3%     28,150,000    310  2026-09-04 14:31  │
│  📁 data-pipeline      $8.60  17.7%     16,400,000    185  2026-09-03 02:43  │
│  📁 frontend-dash      $4.40   9.1%      8,200,000    120  2026-09-01 20:55  │
│  📁 tokenguard         $2.80   5.8%      5,100,000     80  2026-09-04 16:33  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 🖥️ Web Dashboard Preview

Open **`http://localhost:8001/dashboard`** in your browser:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🛡️ TokenGuard  |  🟢 Telemetry Active (8001)  |  [今日 (24h)] [7天] [30天] [全生命周期]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [💰 统计期总花费: $48.50]    [⚡ Token 吞吐: 12.8 M]    [📊 拦截请求: 1,420]   [🟢 运行平稳] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  AI 编程软件专属监控矩阵 (4-Tool Cockpit Matrix):                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ 🟣 Claude Code   │  │ 🟢 Antigravity   │  │ 🔵 ChatGPT       │  │ 🟡 DeepSeek     │ │
│  │ Spent: $22.40    │  │ Spent: $14.60    │  │ Spent: $6.80     │  │ Spent: $4.70    │ │
│  │ Tokens: 5.4 M    │  │ Tokens: 4.8 M    │  │ Tokens: 1.2 M    │  │ Tokens: 1.4 M   │ │
│  │ Context: 42.5%   │  │ Context: 18.2%   │  │ Context: 35.0%   │  │ Context: 68.4%  │ │
│  │ [Safe]           │  │ [Healthy]        │  │ [Safe]           │  │ [Safe]          │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └─────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  📈 每日消费趋势与 Token 轨迹 (SVG Area Chart)   |   🏆 热门模型消费占比排行榜              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  📡 实时请求流水 (Real-time Stream Feed with Token Flow: In → Out & Cost Attribution)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Architecture Overview

```mermaid
graph TD
    subgraph ClientLayer [AI Coding Assistants & Clients]
        C1[Claude Code CLI]
        C2[Antigravity / Gemini 3.7]
        C3[ChatGPT / Codex]
        C4[DeepSeek / Cursor / Windsurf]
    end

    subgraph TokenGuardCore [TokenGuard Industrial Engine :8001]
        Proxy[Async Proxy Forwarding Engine]
        Pool[Global Async HTTP Connection Pool]
        Sniffer[O(1) Streaming Token Sniffer]
        Queue[Bounded Async Queue Drop-Oldest 2000]
        Worker[Background Batch Storage Worker]
        WAL[(Local SQLite WAL ~/.tokenguard/usage.db)]
    end

    subgraph UpstreamProviders [LLM Cloud Endpoints]
        P1[Anthropic API]
        P2[Google Gemini API]
        P3[OpenAI API]
        P4[DeepSeek / Groq / Qwen / GLM]
    end

    subgraph UserInterfaces [Developer Observability]
        Web[Dark OLED Glassmorphism Dashboard]
        CLI[Terminal CLI & Watch Mode]
    end

    ClientLayer -->|Non-Blocking Requests| Proxy
    Proxy -->|Keep-Alive Connection Pool| Pool
    Pool -->|Stream Raw Chunks| UpstreamProviders
    UpstreamProviders -->|Zero-Accumulation SSE| Sniffer
    Sniffer -->|Immediate Chunk Pipe| ClientLayer
    Sniffer -.->|Safe Dispatch| Queue
    Queue -->|Batch WAL Insert| Worker
    Worker --> WAL
    WAL --> Web
    WAL --> CLI
```

---

## 💰 Supported Models & Prompt Caching Engine

TokenGuard features built-in 2025/2026 pricing tables with accurate cache discount calculations:

| Provider | Supported Models | Official Base Rate (In / Out per 1M) | Cache Discount |
|---|---|---|---|
| **Anthropic** | Claude 3.7 / 3.5 Sonnet | $3.00 / $15.00 | **90% Read Discount ($0.30/1M)** |
| **Anthropic** | Claude 3.5 Haiku | $0.80 / $4.00 | **90% Read Discount ($0.08/1M)** |
| **Anthropic** | Claude 3 / 4 Opus | $15.00 / $75.00 | **90% Read Discount ($1.50/1M)** |
| **Google Gemini** | Gemini 3.7 / 2.5 / 2.0 Flash | $0.10 / $0.40 | **75% Cache Discount ($0.025/1M)** |
| **Google Gemini** | Gemini 2.5 / 3.1 Pro | $1.25 / $5.00 | **75% Cache Discount ($0.31/1M)** |
| **OpenAI** | GPT-4o | $2.50 / $10.00 | **50% Read Discount ($1.25/1M)** |
| **OpenAI** | GPT-5.6 Sol (Codex) | $5.00 / $15.00 | **50% Read Discount ($2.50/1M)** |
| **OpenAI** | o3-mini / o1-mini | $1.10 / $4.40 | **50% Read Discount ($0.55/1M)** |
| **DeepSeek** | DeepSeek-V4-Flash / V3 | $0.27 / $1.10 | **74% Cache Hit ($0.07/1M)** |
| **DeepSeek** | DeepSeek-R1 Reasoner | $0.55 / $2.19 | **74% Cache Hit ($0.14/1M)** |
| **Groq / OpenSource** | Llama 3.3 70B, Mixtral | $0.59 / $0.79 | Standard Low-Latency Rates |
| **Chinese Frontier** | Kimi K3, GLM-5.2, Qwen 2.5 | Tiered Official Rates | Regional Pricing & Free Flash Tier |

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).

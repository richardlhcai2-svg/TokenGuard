# TokenGuard

**AI Cost Intelligence** — Proxy, track, and optimize your AI API spending across Anthropic Claude, OpenAI, Google Gemini, and DeepSeek.

```
pip install tokenguard
tg quickstart
tg serve
```

## Quick Start (5 minutes)

1. **Install**
   ```bash
   pip install tokenguard
   ```

2. **Run the wizard**
   ```bash
   tg quickstart
   ```
   This will guide you through setting up your API keys and choosing a run mode.

3. **Start the proxy**
   ```bash
   tg serve
   ```
   TokenGuard starts a proxy on `http://localhost:8001` that intercepts your AI API calls.

4. **Configure your tools**

   | Setting | Value |
   |---------|-------|
   | Base URL | `http://localhost:8001` |
   | Auth Header | `x-tokenguard-key: <your-secret>` |
   | Provider Key | `x-anthropic-key` / `x-openai-key` / `x-gemini-key` / `x-deepseek-key` |

5. **View usage**
   ```bash
   tg stats    # Terminal dashboard
   tg stats --watch  # Live-updating dashboard
   ```

## Commands

| Command | Description |
|---------|-------------|
| `tg quickstart` | Interactive setup wizard |
| `tg serve` | Start standalone proxy (no Docker needed) |
| `tg deploy` | Start full Docker stack (web dashboard + team) |
| `tg stats` | View usage dashboard in terminal |
| `tg config` | View or set configuration |
| `tg --help` | Show all commands |

## Run Modes

### Standalone Mode (`tg serve`)
- No Docker required
- Uses local SQLite storage at `~/.tokenguard/usage.db`
- Terminal dashboard via `tg stats`
- Perfect for individual developers

### Full Stack Mode (`tg deploy`)
- Web dashboard at `http://localhost:3000`
- PostgreSQL + Redis for team features
- Multi-member organization support
- Alert rules and budget tracking

## Supported Providers

- **Anthropic Claude** (Sonnet, Opus, Haiku, Fast)
- **OpenAI** (GPT-4.1, GPT-4o, o-series)
- **Google Gemini** (2.5 Pro, 2.5 Flash)
- **DeepSeek** (V3, R1)

```bash
# Configure for any provider
tg config anthropic_api_key sk-ant-...
tg config openai_api_key sk-...
tg config gemini_api_key AIza...
tg config deepseek_api_key sk-...
```

## Development

```bash
# Install from source
git clone <repo>
cd tokenguard
pip install -e .

# Run tests
cd proxy && python -m pytest tests/ -v
```

## Why TokenGuard?

- **💰 Save money** — See exactly what you're spending per model, per tool, per user
- **🔍 Track everything** — Every API call is logged with token counts and costs
- **🔄 Provider-agnostic** — Single endpoint for all AI providers
- **🛡️ Secure** — Your API keys never leave your infrastructure
- **📊 Insights** — Model recommendations, budget alerts, cost predictions

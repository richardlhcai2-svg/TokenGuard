# 🛡️ TokenGuard

<p align="center">
  <b>面向现代 AI 编程工作流的工业级成本归集中心、上下文风控 HUD 与毫秒级遥测代理</b>
</p>

<p align="center">
  <a href="https://pypi.org/project/tokenguard/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="MIT License"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/%E6%9E%B6%E6%9E%84-Fail--Open%20%7C%20%E9%9B%B6%E9%98%BB%E5%A1%9E%E8%BD%AC%E5%8F%91-00C853.svg?style=flat" alt="Fail Open"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/%E5%86%85%E5%AD%98%E5%8D%A0%E7%94%A8-%3C50MB%20%E6%81%92%E5%AE%9A-6366F1.svg?style=flat" alt="极低内存占用"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/%E7%A9%BA%E8%BD%ACCPU-0.0%25-brightgreen.svg?style=flat" alt="零CPU消耗"></a>
</p>

<p align="center">
  [ <a href="README.md">English</a> ] · [ <b>简体中文</b> ]
</p>

---

## 💡 TokenGuard 解决什么痛点？

现代开发者在重度使用 **Claude Code**、**Antigravity (Gemini)**、**ChatGPT / Codex** 和 **DeepSeek** 等 AI 编码工具时，往往面临三大核心瓶颈：

1. **项目研发账单无法精细归集**：月末收到一份笼统账单，无法准确拆解各个 Git 仓库、独立模块或企业客户的真实消耗占比。
2. **长会话上下文静默爆仓**：多轮会话悄无声息膨胀至数十万 Token，引发模型推理质量退化、触发昂贵的自动 Compact 压缩与天价账单。
3. **传统代理容易断流与内存堆积**：由于大模型 SSE 流式包体积巨大、字符串拼接待定或 SQLite 写入锁争用，经常引发 `ECONNRESET` 断流与 IDE 假死。

**TokenGuard** 借鉴 **OmniRoute** 与 **Envoy** 的工业级无阻塞架构设计，提供 **$O(1)$ 恒定内存流式嗅探、100% Fail-Open 容灾保障**，不仅确保 AI 工具长连接永不断流，更为开发者打造了**深色玻璃拟态 (Dark OLED Glassmorphism) 极具极客品味的 Web 仪表盘**与 **四大 AI 编程软件独立驾驶舱矩阵**。

```bash
pip install tokenguard
tg serve
```

---

## ⚡ 核心架构与功能亮点

### 1. 🛡️ 100% Fail-Open 零阻塞数据平面 (Zero-Blocking Data Plane)
- **转发与存储彻底解耦**：核心 HTTP/SSE 转发通道不依赖数据库与统计计算，确保转发面绝对纯粹。
- **有界异步环形缓冲**：内置高吞吐环形队列（`maxsize=2000`），采用 *Drop-Oldest* 淘汰策略与后台批量 WAL 落盘，即便本地磁盘锁库或极端高并发，**前端业务请求 100% 免受阻，永不发生 `ECONNRESET`**。
- **$O(1)$ 流式嗅探器**：边读边转发流式原始字节，内存零字符串累加，长达数小时的数十万 Token 会话依然轻盈流畅。

### 2. 🎛️ 四大主流 AI 编程软件独立监控矩阵 (4-Tool Matrix Cockpit)
实时呈现各工具的实时代谢速率、上下文窗口负荷百分比（0~100%+）、峰值负载及针对性优化建议：
- 🟣 **Claude Code CLI** (Anthropic Sonnet 3.7 / 3.5, Opus 3/4)
- 🟢 **Antigravity** (Google DeepMind Gemini 3.7 Pro / 2.5 Flash)
- 🔵 **ChatGPT / Codex** (OpenAI GPT-5.6 Sol / GPT-4o / o3-mini)
- 🟡 **DeepSeek** (DeepSeek-V4-Flash / R1 / V4-Pro)

### 3. 📁 全生命周期 Git 仓库与工作区成本归集 (Project Attribution)
- 自动智能嗅探请求来源的 Git 仓库与本地目录（如 `socialmind-ai`、`tokenguard`、`Panstone`、`EngineeringOS`）。
- 精确追踪每个项目从立项第一天起的全生命周期美金花费、Token 吞吐量与请求次数。

### 4. 🎨 极客品味级深色玻璃拟态 Web 仪表盘 (HUD Dashboard)
- **线性设计感 (Linear / Raycast / Vercel 美学)**：高对比度暗黑背景、微光流线阴影与现代排版。
- **动态消费轨迹面积图 (Dynamic SVG Area Chart)**：带有平滑贝塞尔曲线、渐变填充与鼠标悬浮交互卡片。
- **热门模型排行榜与实时流式明细**：呈现 Token 输入输出流向比例（如 `140k → 1.2k`）与单次开销。
- **中英双语无缝切换**：右上角一键切换中文/英文（`中 / EN`）。
- **多维度时间范围**：支持 `今日 (24h)`、`最近 7 天`、`最近 30 天` 与 `全生命周期历史`。

### 5. 🪶 极致低资源占用 (Ultra-Low Footprint)
- **恒定极低内存**：日常运行内存 `< 50MB RAM`，不随流量大小线性递增。
- **零 CPU 空转消耗**：无请求时 CPU 占用稳定在 `0.0%`。
- **100% 本地隐私安全**：所有记录均存储在本地 SQLite WAL（`~/.tokenguard/usage.db`），零外部遥测上报。

---

## 🚀 5 分钟快速上手

### 1. 安装
```bash
pip install tokenguard
```

### 2. 启动代理与仪表盘
```bash
tg serve
```
TokenGuard 将在本地启动 `http://localhost:8001` 代理服务，并在 `http://localhost:8001/dashboard` 提供实时可视化仪表盘。

*(如需在 macOS 后台开机自启，可使用 `tg serve --daemon` 托管至 LaunchAgent)*

### 3. 配置开发工具与代理客户端

#### A. Claude Code CLI
在终端或 Shell 环境中配置 Base URL：
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

#### D. 多模型转发网关 (fcc-server / OmniRoute)
将上游目标指向 `http://localhost:8001`，并附带 TokenGuard 认证 Header：
```http
x-tokenguard-key: <您的代理私钥>
```

---

## 💻 命令行指令大全

| 指令 | 说明 |
|---|---|
| `tg serve` | 启动零阻塞高性能代理服务与 Web 仪表盘（端口 8001） |
| `tg dashboard` | 在默认浏览器中直接打开 Web 仪表盘 |
| `tg stats` | 终端即时输出最近 Token 吞吐与消费明细汇总 |
| `tg stats --watch` | 开启终端实时动态刷新监控表盘（每秒刷新） |
| `tg projects` | 查看全生命周期的项目/工作区成本归集明细表 |
| `tg config` | 查看和配置本地 API 密钥与代理参数 |
| `tg quickstart` | 启动交互式快速配置引导向导 |
| `tg --help` | 查看所有支持的命令与参数选项 |

---

## 🖥️ 仪表盘驾驶舱概览

在浏览器打开 **`http://localhost:8001/dashboard`**：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🛡️ TokenGuard  |  🟢 Telemetry Active (8001)  |  [今日 (24h)] [7天] [30天] [全生命周期]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [💰 统计期总花费: $532.79]   [⚡ Token 吞吐: 3.94 B]   [📊 拦截请求: 28,254]  [🟢 运行平稳] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  AI 编程软件专属监控矩阵 (4-Tool Cockpit Matrix):                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ 🟣 Claude Code   │  │ 🟢 Antigravity   │  │ 🔵 ChatGPT       │  │ 🟡 DeepSeek     │ │
│  │ Spent: $198.52   │  │ Spent: $165.35   │  │ Spent: $48.93    │  │ Spent: $120.10  │ │
│  │ Tokens: 1.84 B   │  │ Tokens: 1.65 B   │  │ Tokens: 7.21 M   │  │ Tokens: 436.9 M │ │
│  │ Context: 78.1%   │  │ Context: 19.5%   │  │ Context: 76.6%   │  │ Context: 208.2% │ │
│  │ [Run /compact]   │  │ [Healthy]        │  │ [Open Thread]    │  │ [Clear History] │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └─────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  📈 每日消费趋势与 Token 轨迹 (动态 SVG 面积图)   |   🏆 热门模型消费占比排行榜             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  📡 实时请求流水 (Real-time Stream Feed with Token Flow: In → Out & Cost Attribution)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 工业级技术架构图

```mermaid
graph TD
    subgraph ClientLayer [AI 编程客户端与辅助工具]
        C1[Claude Code CLI]
        C2[Antigravity / Gemini 3.7]
        C3[ChatGPT / Codex]
        C4[DeepSeek / Cursor / Windsurf]
    end

    subgraph TokenGuardCore [TokenGuard 工业级本地引擎 :8001]
        Proxy[异步代理转发引擎 Async Proxy]
        Pool[全局复用连接池 Global Connection Pool]
        Sniffer[O(1) 零累加流式嗅探器 Stream Sniffer]
        Queue[有界异步环形缓冲 Drop-Oldest Queue]
        Worker[后台批量落盘工作线程 Batch Storage Worker]
        WAL[(本地 SQLite WAL ~/.tokenguard/usage.db)]
    end

    subgraph UpstreamProviders [上游大模型官方接口]
        P1[Anthropic API]
        P2[Google Gemini API]
        P3[OpenAI API]
        P4[DeepSeek / Groq / 通义千问 / 智谱]
    end

    subgraph UserInterfaces [开发者可观测界面]
        Web[深色玻璃拟态 Web 仪表盘]
        CLI[终端命令行与 Watch 监控]
    end

    ClientLayer -->|零阻塞发起调用| Proxy
    Proxy -->|复用 Keep-Alive 连接池| Pool
    Pool -->|流式转发分块| UpstreamProviders
    UpstreamProviders -->|无缓存 SSE 流| Sniffer
    Sniffer -->|实时管道回传分块| ClientLayer
    Sniffer -.->|非阻塞安全分发| Queue
    Queue -->|批量异步写入| Worker
    Worker --> WAL
    WAL --> Web
    WAL --> CLI
```

---

## 💰 全面内嵌官方模型计费与 Prompt Caching 折扣

| 提供商 | 支持模型系列 | 缓存折扣算法 |
|---|---|---|
| **Anthropic** | Claude 3.7 Sonnet、Claude 3.5 Sonnet、Claude 3.5 Haiku、Claude 3/4 Opus | **官方 90% 缓存读取折扣** |
| **Google Gemini** | Gemini 3.7 Pro、Gemini 2.5 Flash、Gemini 2.0 Flash、Gemini 1.5 Pro | **官方 75% 上下文缓存折扣** |
| **OpenAI** | GPT-5.6 Sol、GPT-4o、o1、o3-mini、o4、Codex | **官方 50% 缓存读取折扣** |
| **DeepSeek 深度求索** | DeepSeek-V4-Flash、DeepSeek-V3、DeepSeek-R1 推理模型 | **官方 74% 缓存命中折扣** |
| **Groq / 开源生态** | Llama 3.3 70B、Llama 3.1 8B、Mixtral 8x7B、Gemma 2 9B | 官方极速计费阶梯 |
| **国产大模型矩阵** | Kimi K3、智谱 GLM-5.2 / GLM-4-Plus、阿里通义千问 Qwen 2.5 72B | 分级定价与免费额度智能适配 |

---

## 📄 开源许可证

本项目遵循 [MIT License](LICENSE) 开源协议。

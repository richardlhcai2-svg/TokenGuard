# 🛡️ TokenGuard

<p align="center">
  <b>面向 AI 编程工具的本地原生 AI 成本智能归集与实时上下文风控防护中心</b>
</p>

<p align="center">
  <a href="https://pypi.org/project/tokenguard/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="MIT License"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/%E6%9E%B6%E6%9E%84-%E6%9C%AC%E5%9C%B0%E4%BC%98%E5%85%88%20(Local--First)-00C853.svg?style=flat" alt="本地优先"></a>
  <a href="https://github.com/richardlhcai2-svg/TokenGuard"><img src="https://img.shields.io/badge/%E5%86%85%E5%AD%98%E5%8D%A0%E7%94%A8-~50MB-6366F1.svg?style=flat" alt="极低内存占用"></a>
</p>

<p align="center">
  [ <a href="README.md">English</a> ] · [ <b>简体中文</b> ]
</p>

---

## 💡 TokenGuard 解决什么痛点？

现代开发者在使用 **Claude Code**、**ChatGPT Codex**、**Antigravity (Gemini)**、**Cursor** 等 AI 编程工具时，往往面临两大核心困扰：
1. **项目研发成本无法归集**：月底账单是一个模糊的大总数，无法知道到底是哪个具体的 Git 仓库、项目代码库或客户消耗了这笔预算。
2. **上下文膨胀引发静默爆仓**：长对话过程中 Context 悄无声息膨胀到数十万 Token，触发昂贵的 Compact 压缩、性能大幅下降以及天价账单。

**TokenGuard** 是一款零延迟、极低资源占用的本地原生代理与后台守护中心。它能毫秒级拦截记录 API 消耗，自动扣减 Prompt Caching 折扣，将成本精确归集到每个 Git 项目，并实时计算上下文压力（Context Stress）仪表盘。

```bash
pip install tokenguard
tg serve
```

---

## ✨ 核心特性

- 📁 **按 Git 仓库 / 项目工作区精确归集成本 (Project-Level Cost Attribution)**：自动提取当前请求的工作区路径与项目名称（如 `socialmind-ai`、`tokenguard`），清晰展现每个项目全生命周期与每日的 Token 与美金消耗。
- ⚡ **实时上下文压力表盘 (Real-Time Context Stress)**：动态呈现 0~100% 上下文负荷，设置三色安全阈值（安全绿、警戒黄、爆仓红），在会话即将触发 Compact 压缩前精准告警。
- 💰 **全面内嵌 2025/2026 官方模型定价与缓存折扣**：
  - **Anthropic Claude**：Sonnet 3.7/3.5、Opus 3/4/5、Haiku 3.5（官方 90% 缓存读取折扣）。
  - **Google Gemini**：Flash 3.7/2.5/2.0（$0.10/1M 输入，$0.40/1M 输出）、Pro 2.5/3.1（75% 上下文缓存折扣）。
  - **OpenAI / Codex**：GPT-5.6 Sol（$5/$15）、GPT-4o、o1、o3-mini、o4（50% 缓存折扣）。
  - **DeepSeek 深度求索**：V3 / V4-Flash（$0.27/$1.10，命中缓存仅 $0.07）、R1 / V4-Pro 推理模型（$0.55/$2.19）。
  - **Groq 极速推理**：Llama 3.3 70B（$0.59/$0.79）、Llama 3.1 8B、Mixtral 8x7B、Gemma 2 9B、DeepSeek-R1 Distill。
  - **Moonshot Kimi (月之暗面)**：K3（$0.50/$1.50）、K3-Free（免费节点 $0.00）、Moonshot-v1 系列。
  - **智谱 AI (GLM 系列)**：GLM-5.2、GLM-4-Plus（$0.80/$1.60）、GLM-4-Air、GLM-4-Flash（免费商用）、GLM-4-Long（100 万超长窗口）。
  - **阿里通义千问 (Qwen)**：Qwen 2.5 72B / 32B / Coder / Max / Plus / QwQ-32B。
- 🖥️ **商业级高颜值 Web 仪表盘**：内置深色玻璃拟态多视图切换架构：
  1. `[⚡ 实时仪表与概览]`：实时上下文压力表盘、当日预算与消耗速率、Token 流速。
  2. `[📁 项目成本归集中心]`：独立专属的项目分账总览，呈现各项目全生命周期花费、占比与调用频次。
  3. `[📡 全量请求实时流]`：毫秒级请求流水日志，包含耗时与单次费用。
- 📟 **极速命令行交互**：内置终端动态表盘，支持 `tg stats --watch` 与 `tg projects`。
- 🪶 **极低系统资源常驻 (<0.1% CPU, ~50MB 内存)**：采用 SQLite WAL 并发模式与文件修改时间哈希缓存，对本地磁盘无多余轮询 I/O。
- 🔒 **100% 本地隐私安全**：所有数据均仅保存在本地 SQLite（`~/.tokenguard/usage.db`），零云端上传，无任何远程追踪。

---

## 🚀 5 分钟快速上手

### 1. 安装
```bash
pip install tokenguard
```

### 2. 交互式向导初始化
```bash
tg quickstart
```

### 3. 启动后台代理与仪表盘
```bash
tg serve
```
TokenGuard 将在 `http://localhost:8001` 启动代理服务，并在 `http://localhost:8001/dashboard` 提供可视化表盘。

### 4. 配置您的开发工具（Cursor, Claude Code 等）

| 设置项 | 配置值 |
|---|---|
| **Base URL** | `http://localhost:8001` |
| **认证 Header** | `x-tokenguard-key: <您的代理密钥>` |
| **提供商密钥 Header** | `x-anthropic-key` / `x-openai-key` / `x-gemini-key` / `x-deepseek-key` *(亦可在 `tg config` 中集中配置)* |

---

## 💻 命令行指令大全

| 指令 | 说明 |
|---|---|
| `tg serve` | 启动独立代理服务与 Web 仪表盘（端口 8001） |
| `tg dashboard` | 在默认浏览器中直接打开 Web 仪表盘 |
| `tg stats` | 在终端中查看最近 7 天 Token 消耗与成本统计 |
| `tg stats --watch` | 开启终端实时动态刷新监控表盘（每秒刷新） |
| `tg projects` | 查看全生命周期的项目/工作区成本归集明细表 |
| `tg config` | 查看和配置本地 API 密钥与代理参数 |
| `tg quickstart` | 启动交互式快速配置引导向导 |
| `tg --help` | 查看所有支持的命令与参数选项 |

---

## 📁 项目成本归集呈现示例

```text
╭────────────── 📁 Project Cost Attribution (All-Time Lifetime) ───────────────╮
│                📁 AI Cost Attribution by Project / Workspace                 │
│  Project /                                                                   │
│  Workspace             Spent  Share         Tokens  Calls  Last Active       │
│  📁 socialmind-ai    $401.57  38.4%  2,962,375,275  30324  2026-08-30 15:05  │
│  📁 Panstone         $203.71  19.5%     35,912,380    118  2026-08-30 14:31  │
│  📁 AiforFA          $102.36   9.8%    797,240,913   8457  2026-08-30 02:43  │
│  📁 EngineeringOS     $64.94   6.2%    424,191,128   4386  2026-08-21 20:55  │
│  📁 tokenguard        $27.18   2.6%    258,985,816   1046  2026-08-30 16:33  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。

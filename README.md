# PikaClaude

一个本地优先（local-first）的双进程 AI Agent 系统。`pika-core` 作为常驻守护进程承载 agent 运行时，`pika`（CLI）与 `pika-tui`（TUI）通过 TCP loopback 上的 JSON-RPC 2.0 (NDJSON) 与之通信。

## 特性

- **双进程架构** — Agent 运行时与用户界面解耦：daemon 持久运行，CLI/TUI 随用随起
- **Plan → Act → Observe 循环** — 基于 Anthropic Messages API 的工具调用 agent loop，支持流式响应与 prompt caching
- **工具系统** — 内建 `read_file` / `write_file` / `list_dir` / `bash` / `note_save` 及 `task_*` 系列任务管理工具，按需启用
- **权限审批** — 四层静态策略（deny / outside-cwd / allow / default）+ 运行时交互式审批，写操作默认 `ASK`，读操作默认 `ALLOW`
- **MCP 集成** — 通过 Model Context Protocol 接入外部工具服务器（stdio / tcp），自动发现并注册工具
- **子 Agent 派生** — `spawn_agent` 工具支持前台阻塞或后台并行执行隔离的冷启动子任务
- **Agent Profiles** — TOML 角色配置（planner / executor / reviewer），按三级优先级覆盖：项目本地 > 用户全局 > 内建
- **Skills** — Markdown frontmatter 定义的可复用 system prompt 模板，支持 `$ARGUMENTS` 参数注入
- **会话管理** — 多轮对话持久化（`~/.pika/sessions/`），支持 `chat` / `one_shot` 两种模式
- **上下文压缩** — 自动/手动 compact，将长对话摘要为六段式 handoff summary，支持 tool_result 截断
- **可观测性** — 全链路 trace（IPC / event / LLM 层），事件流持久化为 `events.jsonl`，支持回放
- **TUI 前端** — 基于 Textual 的终端界面，是主要的用户交互入口

## 架构

```
┌─────────────┐   ┌──────────────┐
│  pika (CLI) │   │ pika-tui(TUI)│
└──────┬──────┘   └──────┬───────┘
       │ JSON-RPC 2.0 NDJSON (TCP 127.0.0.1:7437)
       └────────┬────────┘
                ▼
       ┌────────────────────────────────────────┐
       │              pika-core (daemon)        │
       │  ┌──────────┐  ┌───────────┐           │
       │  │ SocketServer │ EventBus │  Trace    │
       │  └────┬─────┘  └─────┬─────┘           │
       │       │              │                 │
       │  ┌────▼──────────────▼─────────────┐   │
       │  │   SessionManager / AgentRunner  │   │
       │  │   ┌──────────────────────────┐  │   │
       │  │   │  AgentLoop (plan/act/obs)│  │   │
       │  │   └──────────┬───────────────┘  │   │
       │  │   ToolRegistry │ Compactor       │   │
       │  │   PermissionManager │ McpManager │   │
       │  └──────────────────────────────────┘  │
       └────────────────────────────────────────┘
```

## 环境要求

| 依赖 | 版本 |
|------|------|
| 操作系统 | macOS / Linux（主），Windows 可运行 |
| Python | 3.12.x |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.4 |

安装 uv（若尚未安装）：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Python 3.12 由 uv 自动管理，无需手动安装。

## 快速开始

```bash
git clone <repo> && cd PikaClaude
uv sync                         # 安装依赖
cp .env.example .env            # 按需修改（如填入 ANTHROPIC_API_KEY）

uv run pika-core                # 启动守护进程（前台，Ctrl+C 退出）
uv run pika ping                # 验证连通：应返回 pong
uv run pika --version           # 应输出 0.0.1
```

另起一个终端：

```bash
uv run pika run --goal "列出当前目录下所有 Python 文件并统计总行数"
uv run pika chat                # 多轮对话
uv run pika-tui                 # 启动 TUI（主前端）
```

## CLI 命令参考

| 命令 | 说明 |
|------|------|
| `pika ping` | 探活守护进程 |
| `pika --version` | 打印版本 |
| `pika run --goal "..."` | 执行一次性 agent 任务 |
| `pika chat` | 进入多轮对话会话 |
| `pika core start` | 后台启动守护进程 |
| `pika core stop` | 停止守护进程 |
| `pika core status` | 查看守护进程状态 |
| `pika trace [run_id]` | 查看 trace 日志（支持 `--layer` / `--direction` / `--follow` / `--raw`） |
| `pika-tui` | 启动 TUI 前端 |

## 配置

优先级（低 → 高）：**内建默认值 → `~/.pika/config.toml` → 项目本地 `.pika/config.toml` → `.env` → 系统环境变量**。

### `~/.pika/config.toml`

```toml
[core]
host = "127.0.0.1"
port = 7437

[logging]
level  = "INFO"
file   = "~/.pika/logs/core.log"
format = "text"    # "text" | "json"

[agent]
max_steps = 20

[llm]
default_model = "claude-sonnet-4-6"

[trace]
enabled = true
include_llm_payload = true

[permission]
timeout_s = 60.0

[compaction]
auto_threshold = 0.0      # 0 表示禁用自动压缩，推荐用 /compact
tool_result_limit = 8000
tool_result_keep = 4000
```

### 主要环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANTHROPIC_API_KEY` | — | Anthropic API 密钥 |
| `PIKA_CONFIG` | `~/.pika/config.toml` | 配置文件路径 |
| `PIKA_HOST` | `127.0.0.1` | TCP 监听地址 |
| `PIKA_PORT` | `7437` | TCP 监听端口 |
| `PIKA_LOG_LEVEL` | `INFO` | 日志级别 |
| `PIKA_LOG_FILE` | `~/.pika/logs/core.log` | 日志文件（留空仅输出 stderr） |
| `PIKA_LOG_FORMAT` | `text` | 日志格式（`text` / `json`） |

## 目录布局

```
~/.pika/
├── config.toml              # 全局配置
├── context.md               # 全局上下文（每次 run 注入）
├── policy.toml              # 权限策略持久化（remember 决策）
├── agents/<name>.toml       # 用户全局 Agent Profile
├── skills/<name>.md         # 用户全局 Skill
├── sessions/<session_id>/
│   ├── thread.jsonl         # 会话消息历史
│   ├── notes/               # note_save 工具产物
│   └── runs/<run_id>/
│       └── events.jsonl     # 该 run 的事件流
├── logs/core.log
└── traces/daemon.jsonl      # 全链路 trace

.pika/                       # 项目本地覆盖（优先级高于全局）
├── context.md
├── agents/<name>.toml
└── skills/<name>.md
```

## 开发

```bash
make lint                    # ruff + mypy
make test                    # 单元测试
make integration-test        # 集成测试（自动 spawn 真实 daemon）
make docs                    # 重新生成 WIRE_PROTOCOL.md
make verify-s0               # 完整验证（lint + 类型 + 测试 + 协议同源检查）

# 单测
uv run pytest tests/unit/test_envelope.py::test_request_roundtrip -v
```

代码风格：所有函数上方须有**单行中文注释**说明其职责；测试函数上方须有 `# 功能：` 与 `# 设计：` 两行注释。详见 [AGENT.md](./AGENT.md)。

## 文档

- **[RUNBOOK.md](./RUNBOOK.md)** — 运维手册：配置、日常操作、日志、常见错误
- **[AGENT.md](./AGENT.md)** — 开发指南：架构、协议层、代码风格、测试约定

## 技术栈

- **运行时** — Python 3.12 / asyncio / pydantic v2
- **LLM** — Anthropic SDK（流式 + prompt caching）
- **TUI** — Textual + Rich
- **构建** — Hatchling / uv workspace
- **质量** — ruff / mypy strict / pytest + pytest-asyncio

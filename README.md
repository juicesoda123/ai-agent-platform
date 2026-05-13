---
title: Nexus AI Agent Platform
emoji: 
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
---

# Nexus AI Agent Platform

> 从零搭建的生产级 AI Agent 平台。44 个工具，4 个模型，3 种推理模式，完整的安全护栏和可观测性。

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.57-red)](https://streamlit.io)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V4_Pro-green)](https://deepseek.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Demo

```
Q: 搜索 GitHub 上最火的 LangGraph 项目，看怎么用在 Agent 里

Agent:
  web_search("LangGraph github stars")  → 找到 langgraph 仓库
  fetch_page("github.com/langchain-ai/langgraph") → 读 README
  search_knowledge("LangGraph Agent")   → 查本地31篇笔记

💭 Reflexion 自我批判: "缺少代码示例，需要补充"
💭 修正后: [含代码的完整回答 + 来源链接]
```

---

## 核心特性

### 推理引擎
- **3 种推理模式** — 标准 ReAct / Reflexion 自我批判 / 多路生成+人机投票
- **流式输出** — DeepSeek SSE 实时 token 渲染
- **4 个模型** — deepseek-chat / deepseek-reasoner / deepseek-v4-pro / deepseek-v4-flash
- **温度调节** — 0=精确 1.5=创意

### 工具生态 (44 tools)
| 类别 | 数量 | 来源 |
|------|------|------|
| 联网搜索 + 网页抓取 | 2 | 自建 (DDGS + BeautifulSoup) |
| Python 代码执行 | 1 | 自建 (沙箱 + 超时) |
| 本地文件系统 | 14 | MCP Filesystem Server |
| GitHub 操作 | 28 | MCP GitHub Server |
| 结构化推理 | 1 | MCP Sequential Thinking |
| 知识库检索 | 1 | 自建 RAG (31 篇笔记) |

### 安全护栏
- **InputGuard** — 8 条 jailbreak 正则 + 长度限制
- **OutputGuard** — API Key/手机/身份证/邮箱 自动脱敏
- **ToolGuard** — 工具白名单 + 参数约束
- **PII Scanner** — 10 种隐私信息检测 (Luhn 算法校验信用卡)
- **bcrypt** — 密码加盐存储

### 可观测性 & 成本
- **LangFuse** — 每次 LLM 调用全链路 Trace
- **Cost Tracker** — 7 模型定价表，日/月预算告警 + 自动降级
- **Logger** — 按天轮转日志文件

### 产品体验
- 科幻 UI + 动态星空背景 + 明暗主题
- 注册/登录 + SQLite 多用户记忆
- 对话历史管理 + 单条删除 + 确认弹窗
- 导出对话 (Markdown)
- Ctrl+Enter 发送
- 26 自动化测试

---

## 项目架构

```
AI-Agent/
├── agent-platform/             ← 核心产品
│   ├── src/agent_platform/
│   │   ├── ui.py               Streamlit 主界面
│   │   ├── guardrails.py       安全护栏
│   │   ├── pii.py              PII 检测脱敏
│   │   ├── tracing.py          LangFuse 可观测
│   │   ├── cost.py             成本控制
│   │   ├── server.py           FastAPI 端点
│   │   ├── web_search.py       DDGS 搜索
│   │   ├── web_fetch.py        网页抓取
│   │   ├── code_exec.py        Python 沙箱
│   │   ├── mcp_bridge.py       MCP 协议桥
│   │   ├── advanced.py         Reflexion+多路
│   │   ├── engine.py           共享推理引擎
│   │   └── logger.py           日志系统
│   ├── tests/run_all.py        26 自动化测试
│   ├── Dockerfile
│   └── docker-compose.yml
├── single-agent/               ← ReAct + ToolRegistry
├── multi-agent/                ← BaseAgent + Supervisor
├── mcp-server/                 ← MCP Server/Client
├── rag-system/                 ← RAG 管线
├── route/                      ← 31 篇学习笔记
└── README.md
```

---

## 快速开始

### 1. 环境
```bash
Python 3.12+
Node.js 24+ (MCP 工具需要)
```

### 2. 配置
```bash
cd agent-platform
cp .env.example .env
# 编辑 .env，填入:
#   DEEPSEEK_API_KEY=sk-...
#   LANGFUSE_SECRET_KEY=sk-lf-...  (可选)
#   LANGFUSE_PUBLIC_KEY=pk-lf-...  (可选)
```

### 3. 启动
```bash
pip install -r requirements.txt
PYTHONPATH="src;../single-agent/src;../mcp-server;../rag-system/src" \
  streamlit run src/agent_platform/ui.py
```

打开 http://localhost:8501

### 4. 运行测试
```bash
cd agent-platform
PYTHONPATH="src;../single-agent/src" python tests/run_all.py
# RESULTS: 26 passed, 0 failed
```

---

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | Streamlit 1.57 + 自定义 CSS/JS |
| LLM | DeepSeek API (OpenAI SDK) |
| 工具协议 | MCP (Model Context Protocol) |
| 数据库 | SQLite (用户 + 对话) |
| 向量检索 | all-MiniLM-L6-v2 + numpy |
| 可观测 | LangFuse |
| 安全 | bcrypt, HTML sanitize, PII regex |
| 容器化 | Docker + docker-compose |

---

## 开发路线

| Phase | 内容 | 天数 |
|-------|------|------|
| 1 | Python 工程架构 | 7 |
| 2 | LLM API 封装 | 5 |
| 3 | RAG 检索增强生成 | 6 |
| 4 | 单 Agent 推理引擎 | 4 |
| 5 | Multi-Agent 协作 + MCP 协议 | 3 |
| 6 | 安全护栏 / 可观测 / 容器化 | 7 |

**完整开发笔记：31 个模块，覆盖从 API 封装到生产部署的全链路。**

---

## License

MIT

# AI Agent 高级开发工程师 — 学习路线图

> **学员画像**：具备 ML/DL 理论知识，Python 基础语法掌握但不熟练，OOP/线程/异步等工程能力薄弱。
> **目标终点**：能独立设计、开发、评估、部署生产级 AI Agent 系统。
> **学习方式**：项目驱动，每个 Phase 产出可运行的代码，不是一个"看完的视频列表"。

---

## 总时长估算

按每天 2-4 小时投入计算：

| Phase | 内容 | 预计工作日 | 累计 |
|-------|------|-----------|------|
| 1 | Python 工程补强 | 5-7 天 | 1.5 周 |
| 2 | LLM API 编程 | 5-7 天 | 3 周 |
| 3 | RAG 系统 | 7-10 天 | 5 周 |
| 4 | 单 Agent 开发 | 10-14 天 | 8 周 |
| 5 | Multi-Agent + MCP | 10-14 天 | 11 周 |
| 6 | 生产化部署 | 7-10 天 | 13 周 |

**总计：约 3 个月（13 周），从"会一点 Python"到"能独立交付 AI Agent 项目"。**

> 这个估算是**工程能力 + AI 能力同步拉通**的时间。你的 ML/DL 理论底子是加速器——别人还要补"损失函数是什么"，你已经可以直接看 Agent 的 loss design。

---

## Phase 1：Python 工程补强（5-7 天）

### 目标
不是重学 Python，是把 AI 开发最吃紧的工程能力拉到及格线。

### 你要补齐的东西

| 知识点 | 为什么重要（AI Agent 里的应用） |
|--------|------------------------------|
| **类型注解 (Type Hints)** | Agent 的工具定义、Function Calling 的 schema 全靠类型推导 |
| **OOP（类/继承/抽象基类）** | 设计 BaseAgent → RAGAgent → MultiAgent 的继承体系 |
| **async/await 异步编程** | LLM API 调用是 I/O 密集型，不用异步你的 Agent 卡成狗 |
| **Pydantic 数据模型** | LangChain/LlamaIndex 的标配，结构化输出验证 |
| **异常处理** | LLM 返回不符合预期时不会崩，重试机制是基本素养 |
| **项目结构（模块/包）** | 一个 Agent 项目 20+ 文件，不会拆模快就写成一坨 |

### 产出项目
`ai-foundation/` — 一个标准化的 Python AI 项目骨架，包含：
- 抽象基类 `BaseLLMClient`
- OpenAI/DeepSeek 两种实现
- 异步调用 + 重试机制
- 配置管理（环境变量/pydantic-settings）
- 完整的类型注解

### D1-D7 每日拆解

```
D1: 环境搭建 + 项目结构 + 类型注解
D2: OOP 核心 — 继承/多态/抽象基类
D3: Pydantic — 数据验证/配置管理
D4: 异步编程 — async/await/asyncio
D5: 异常处理 + 重试机制
D6: 综合实战 — BaseLLMClient + OpenAI 实现
D7: 综合实战 — DeepSeek 实现 + 完整串联
```

---

## Phase 2：LLM API 编程（5-7 天）

### 目标
深入 LLM 的 API 层，能写出工业级的 LLM 调用代码。

### 你要补齐的东西

| 知识点 | 为什么重要 |
|--------|-----------|
| **Chat Completion API** | 所有 LLM 对话的底层接口 |
| **Streaming（流式输出）** | 用户体验核心——一个字一个字往外蹦 |
| **Token 计数与管理** | 成本控制 + Context Window 管理 |
| **Function Calling / Tool Use** | Agent 调用工具的底层机制 |
| **System Prompt 设计** | Agent 的行为边界、角色定义全在这 |
| **多模型适配** | Claude/OpenAI/DeepSeek 接口差异，怎么写适配层 |

### 产出项目
`llm-client/` — 一个统一的多模型 LLM 客户端库：
- 统一的 `ChatLLM` 接口，屏蔽不同 API 差异
- 流式/非流式切换
- Token 计数和自动裁剪
- Tool Calling 封装
- 完整的错误处理和重试

### D1-D7 每日拆解

```
D1: Chat API 深入 — messages/system/user/assistant 结构
D2: 流式输出 — SSE 协议 + async generator
D3: Token 管理 — tiktoken + Context Window 自动裁剪
D4: Function Calling 底层 — JSON Schema → Tool Definition
D5: 多模型统一接口 — OpenAI/DeepSeek/Claude 适配
D6: 综合实战 — 一个 CLI 对话机器人
D7: 评测 — 三个模型的响应质量/速度/成本对比
```

---

## Phase 3：RAG 系统（7-10 天）

### 目标
从零搭建一个工业级 RAG 系统，理解每个环节的技术细节和优化手段。

### 你要补齐的东西

| 知识点 | 为什么重要 |
|--------|-----------|
| **Embedding 模型选型** | 中文用哪个、英文用哪个，向量维度对检索精度的影响 |
| **向量数据库** | ChromaDB（开发）→ Milvus/pgvector（生产） |
| **Chunking 策略** | 固定大小 / 语义切割 / 递归切割，哪个场景用哪个 |
| **检索策略** | 向量检索 / BM25 关键词 / Hybrid Search / Re-rank |
| **RAG 评估** | RAGAS 框架 — Faithfulness/Relevance/Precision/Recall |
| **高级 RAG** | Query Rewrite / Multi-hop / Self-RAG / Graph RAG |

### 产出项目
`rag-system/` — 一个可配置的 RAG 知识库问答系统：
- 文档解析（PDF/Markdown/网页）
- 多策略 Chunking
- ChromaDB 向量存储
- Hybrid Search + Re-rank
- RAGAS 评估报告
- Streamlit 可视化界面

### D1-D10 每日拆解

```
D1: 文档加载与解析 — PyPDF/Unstructured/markdown
D2: Chunking 策略对比实验 — 3种策略+可视化对比
D3: Embedding — 模型选型/批量向量化/COS相似度基础
D4: ChromaDB — CRUD/元数据过滤/批量操作
D5: 检索管线 — 单路→多路→Hybrid→Re-rank 逐级搭建
D6: LLM 生成层 — Prompt Template/引用来源/防幻觉约束
D7: RAGAS 评估 — 评估指标+测试集构建+评估报告
D8: 高级 RAG — Query Rewrite/Multi-hop 实验
D9: 前端 — Streamlit 完整对话界面
D10: 整合测试 + 性能分析 + 优化建议文档
```

---

## Phase 4：单 Agent 开发（10-14 天）

### 目标
掌握 Agent 的核心范式，能独立设计和实现一个自主 Agent。

### 你要补齐的东西

| 知识点 | 为什么重要 |
|--------|-----------|
| **ReAct 范式** | Reason + Act：Agent 思考和行动的核心循环 |
| **Tool 体系设计** | 工具定义/注册/调用/结果处理的完整架构 |
| **Agent 记忆系统** | 短期（对话历史）+ 长期（向量库持久化） |
| **Planning 策略** | Task decomposition / Plan-and-Execute / Reflexion |
| **Agent 评估** | 任务成功率 / 工具调用准确率 / 步骤效率 |
| **LangChain/LangGraph** | 工业级 Agent 框架的用法 |

### 产出项目
`single-agent/` — 一个多功能自主 Agent：
- ReAct 核心循环
- 工具：搜索/计算器/代码执行/文件操作/数据库查询
- 短期+长期记忆
- Plan-and-Execute 复杂任务拆解
- 任务执行 trace 可视化
- 评估 benchmark

### D1-D14 每日拆解

```
D1: ReAct 纸上推演 — 手动走一遍 Think→Act→Observe 循环
D2: 最简 ReAct Agent（硬编码3个工具，不依赖框架）
D3: Tool 注册机制 — ToolRegistry/工具 Schema 自动生成
D4: 工具扩展 — 代码执行器/文件系统/搜索引擎
D5: 短期记忆 — 对话历史管理/Token 裁剪策略
D6: 长期记忆 — 向量库存储/记忆检索/遗忘机制
D7: Plan-and-Execute — 复杂任务自动拆解
D8: Reflexion — 失败后自我反思+重规划
D9: LangGraph 入门 — StateGraph/Node/Conditional Edge
D10: 用 LangGraph 重构 Agent
D11: Trace 可视化 — 每次任务执行的完整链路图
D12: 评估体系 — 构建测试集+自动化评分
D13: 边界 case 测试 — 超长任务/恶意指令/无限循环
D14: 文档 + 演示录制
```

---

## Phase 5：Multi-Agent + MCP（10-14 天）

### 目标
掌握多 Agent 协作架构和 MCP 协议，能设计复杂 Agent 系统。

### 你要补齐的东西

| 知识点 | 为什么重要 |
|--------|-----------|
| **Multi-Agent 架构** | Peer-to-peer / Hierarchical / Swarm 三种拓扑 |
| **Agent 间通信** | 消息传递 / 共享记忆 / 任务分发 |
| **MCP 协议** | Client-Server 模型 / Tool/Resource/Prompt 三类能力 |
| **MCP Server 开发** | 自定义 MCP Server 封装业务能力 |
| **Agent 编排** | Supervisor / Swarm / 投票 / 流水线 |
| **人机协同** | Human-in-the-loop / 审批节点 / 权限控制 |

### 产出项目
`multi-agent/` — 一个多 Agent 协作系统：
- 3 个角色 Agent：Researcher/Coder/Reviewer
- Supervisor 调度器
- MCP Server 封装数据库和文件系统
- 完整的任务分发→执行→审查→交付流水线
- 人机审批节点

### D1-D14 每日拆解

```
D1: Multi-Agent 架构设计 — 画出拓扑图+通信协议
D2: 消息协议 — AgentMessage 定义/路由/序列化
D3: 角色 Agent — Researcher Agent（搜索+总结）
D4: 角色 Agent — Coder Agent（写代码+运行）
D5: 角色 Agent — Reviewer Agent（审查+反馈）
D6: Supervisor 调度器 — 任务分发/优先级/冲突处理
D7: 共享记忆 — 多个 Agent 共享上下文
D8: MCP 协议深入 — 规范精读 + 官方示例跑通
D9: MCP Server 开发 — 数据库 MCP Server
D10: MCP Server 开发 — 文件系统 MCP Server
D11: Agent 集成 MCP — 动态发现+调用 MCP 工具
D12: Human-in-the-loop — 审批节点/权限升级
D13: 端到端测试 — 给一个复杂需求看完整协作流程
D14: 性能分析 + 架构文档
```

---

## Phase 6：生产化部署（7-10 天）

### 目标
把前面的 Demo 变成能上生产线的系统。

### 你要补齐的东西

| 知识点 | 为什么重要 |
|--------|-----------|
| **安全护栏 (Guardrails)** | 注入检测 / 越狱防护 / 输出审核 / PII 脱敏 |
| **可观测性** | 日志 / 追踪 / 指标 / LangSmith/LangFuse |
| **成本控制** | Token 预算 / 模型降级 / 缓存策略 |
| **性能优化** | 异步并发 / 批处理 / 连接池 / Prompt Cache |
| **Docker 容器化** | 标准化部署，告别"我机器上能跑" |
| **API 服务化** | FastAPI 封装 Agent 为 HTTP 服务 |
| **CI/CD** | 评估基准自动化测试 / 构建/部署流水线 |

### 产出项目
`agent-platform/` — 一套可部署的 Agent 服务平台：
- FastAPI 服务层（Agent as API）
- Guardrails 安全中间件
- LangFuse 可观测性集成
- Token 成本仪表盘
- Docker Compose 一键部署
- CI 自动化评估流水线

### D1-D10 每日拆解

```
D1: 安全护栏 — 输入清洗/越狱检测/输出审核
D2: PII 脱敏 — 命名实体识别+自动脱敏
D3: 可观测性 — LangFuse 接入/Trace/指标面板
D4: 成本控制 — Token 预算/降级策略/语义缓存
D5: FastAPI — Agent 接口封装/RESTful API 设计
D6: 异步并发 — 连接池/批处理/负载测试
D7: Docker — 容器化+多服务编排
D8: CI/CD — GitHub Actions 自动化评估+部署
D9: 压测 + 稳定性测试
D10: 全栈整合 + 上线 Checklist
```

---

## 学习纪律（不遵守 = 假勤奋）

1. **每个 Phase 产出可运行的代码**，不是笔记，不是"我懂了"
2. **每天的任务完成了才算过**，不积累到明天
3. **遇到问题先自己想 15 分钟**，然后立刻问——别卡半天不说话
4. **每一个 Phase 结束有 Review**——我看你的代码，告诉你哪里可以写得更好
5. **不跳步**。Phase 1 的 OOP 没吃透，Phase 4 的 Agent 继承体系你写不出来

---

## 今天开始：Phase 1 Day 1

你现在需要做的事：

- [ ] 确认 Python 版本（3.10+）
- [ ] 确认 IDE（VS Code / PyCharm / Cursor）
- [ ] 确认 API Key（至少有一个：OpenAI / DeepSeek / 其他）

准备好了告诉我，即刻开工。

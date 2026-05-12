# Day 13 — Phase 2 Review + Phase 3 启动

> Phase 2 收尾  |  预计用时：30 分钟  |  2026-05-05

---

## Phase 2 回顾：你写了什么

```
llm-client/
├── src/llm_client/
│   ├── chat.py       ← ChatSession：多轮对话 / 流式 / Token 裁剪 / 工具调用
│   ├── tools.py      ← Tool 类 + Calculator + Search 工具
│   └── client.py     ← create_client() 工厂函数
└── examples/
    ├── test_multiturn.py        ← D1: 多轮记忆验证
    ├── test_stream.py           ← D2: 流式输出验证
    ├── test_token_limit.py      ← D3: Token 裁剪验证
    ├── test_tool_calling.py     ← D4: 工具调用验证
    ├── cli_full.py              ← D5: 完整 CLI
    └── test_d12.py              ← D5: 流式+工具综合验证
```

| 日 | 主题 | 核心收获 |
|----|------|---------|
| D1 | Chat API + Messages | LLM 是无状态的，"记忆"是把历史塞回去 |
| D2 | 流式 SSE | `stream=True` + `async for`，用户体验质变 |
| D3 | Token 管理 | tiktoken + 自动裁剪，守住 Context Window |
| D4 | Function Calling | 模型不执行函数，只输出 JSON 告诉你要调什么 |
| D5 | 完整 CLI | 工厂模式 + send_stream_with_tools，全链路打通 |

---

## 你现在的代码能力

十几天的代码，你现在能：

- 用 `ChatSession` 管理多轮对话（自动记忆 + Token 裁剪）
- 用 `send_stream()` 做流式输出
- 用 `send_with_tools()` 让模型调用 calculator 和 search
- 用 `create_client()` 一行代码切换 DeepSeek/OpenAI

**这是 Phase 3 的地基。** Phase 3 不做新架构，只做一件事：把 `search()` 从假数据换成**真实的 RAG 检索**。

---

## Phase 3 预告：RAG 系统

```
今天的 search():
  return "搜索结果（模拟）: ..."          ← 假数据

Phase 3 结束后的 search():
  1. 调 Embedding API 把 query 转向量
  2. 在向量数据库里检索 Top-K 文档
  3. 把文档拼成 context 返回给模型
```

Phase 3 技术栈：
- **Embedding**：`text-embedding-3-small` / 本地模型
- **向量数据库**：ChromaDB（开发）/ Milvus（生产）
- **文档处理**：PDF/Markdown 解析 + Chunking
- **检索策略**：向量检索 → Hybrid Search → Re-rank
- **评估**：RAGAS（Faithfulness / Relevance）

D1 会是文档加载 + Chunking。准备好进 Phase 3 吗？

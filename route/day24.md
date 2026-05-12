# Day 24 — MCP 协议：Agent 工具的 USB-C 接口

> Phase 5：Multi-Agent + MCP  |  预计用时：50 分钟  |  2026-05-05

---

## 今日目标

1. 理解 MCP 的本质——用统一协议暴露工具，让任何 Agent 都能调用
2. 搭建一个 MCP Server（把 calculator 和 search_rag 暴露出去）
3. 实现 MCP Client——Agent 通过协议发现和调用远程工具
4. 产出：`mcp-server/` + Agent 通过 MCP 调工具

---

## 一、概念对齐：为什么需要 MCP

**没有 MCP 的现状**：
```
Agent A 项目 ──→ ToolRegistry(calculator, search)
Agent B 项目 ──→ ToolRegistry(calculator, file_reader)
                    ↑
          同一个 calculator 写了两个 Pydantic Model
```

**有了 MCP 之后**：
```
Agent A ──→ MCP Client ──→ MCP Server (tools: calculator, search, file, db)
Agent B ──→ MCP Client ──↗
              ↑
          工具写一次，所有 Agent 共享
```

核心协议：**JSON-RPC over stdio/HTTP**。Server 启动 → Client 连接 → `tools/list` 发现工具 → `tools/call` 执行。

---

## 二、动手实战（35 分钟）

### 任务 1：搭 MCP Server

在 `AI-Agent/` 下新建 `mcp-server/`：

```
mcp-server/
├── .env               ← API Key 配置（不提交 Git）
├── server.py          ← MCP Server 主文件
└── test_mcp.py        ← 验证脚本
```

> `.env` 文件用 `python-dotenv` 的 `load_dotenv()` 加载，把 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` 注入到 `os.environ`。Agent 部分的 `AsyncOpenAI(...)` 通过 `os.getenv(...)` 读取。这样做的好处是：API Key 不硬编码在代码里，`.gitignore` 里加 `.env` 防止泄露。

**`server.py`**——一个最简 MCP Server，暴露 calculator 工具：

```python
"""最简 MCP Server —— 暴露 calculator 工具。

MCP 协议核心：用 JSON-RPC 通信，stdio 传输。
Server: 启动 → 等待请求 → 处理 → 返回结果
"""

import json
import sys


def calculator(expression: str) -> str:
    expression = expression.replace("^", "**")
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "表达式包含不安全字符"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"


# MCP 工具定义
TOOLS = {
    "calculator": {
        "name": "calculator",
        "description": "执行数学计算。参数：{\"expression\": \"数学表达式，如 3**5+100\"}",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式",
                }
            },
            "required": ["expression"],
        },
    },
}


def handle_request(request: dict) -> dict:
    """处理 MCP JSON-RPC 请求。"""
    method = request.get("method")
    req_id = request.get("id")

    # tools/list —— 告诉 Client 有哪些工具
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": list(TOOLS.values())},
        }

    # tools/call —— Client 要调工具
    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "calculator":
            result = calculator(**arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result}]},
            }

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知工具: {tool_name}"}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知方法: {method}"}}


def main():
    """MCP Server 主循环——从 stdin 读请求，从 stdout 写响应。"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as e:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
```

### 任务 2：MCP Client + Agent 集成

**`test_mcp.py`**——用 MCP Client 连接 Server，Agent 通过 MCP 调工具：

```python
"""验证 MCP Client —— Agent 通过协议调用远程工具。"""
import asyncio
import json
import subprocess
import sys
import threading

class MCPClient:
    """MCP 客户端——连接 Server，发现和调用工具。"""

    def __init__(self, server_cmd: list[str]):
        # 启动 Server 子进程，通过 pipe 通信
        self.process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._id = 0
        self._stderr_lines: list[str] = []
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_stderr(self):
        """后台线程持续读取 stderr，防止缓冲区满导致子进程死锁。"""
        for line in self.process.stderr:
            self._stderr_lines.append(line.rstrip())

    def get_stderr(self) -> str:
        """获取子进程 stderr 日志。"""
        return "\n".join(self._stderr_lines)

    def _send(self, method: str, params: dict | None = None) -> dict | str:
        """发送 JSON-RPC 请求，返回响应。"""
        self._id += 1
        request = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params:
            request["params"] = params

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        if "error" in response:
            stderr_log = self.get_stderr()
            detail = f"Error: {response['error']}"
            if stderr_log:
                detail += f"\n[stderr]: {stderr_log}"
            return detail
        return response.get("result", {})

    def list_tools(self) -> list[dict]:
        result = self._send("tools/list")
        if isinstance(result, str):
            return []
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._send("tools/call", {"name": name, "arguments": arguments})
        if isinstance(result, str):
            return result
        contents = result.get("content", [])
        return contents[0]["text"] if contents else str(result)

    def close(self):
        self.process.terminate()


async def main():
    # 1. 启动 MCP Server（用脚本所在目录的相对路径，不受 CWD 影响）
    from pathlib import Path
    server_path = Path(__file__).parent / "server.py"
    client = MCPClient([sys.executable, str(server_path)])

    # 2. 发现工具
    tools = client.list_tools()
    print(f"发现的工具: {[t['name'] for t in tools]}\n")

    # 3. 直接调工具（模拟 Agent 的行为）
    print("=== 直接调 calculator ===")
    result = client.call_tool("calculator", {"expression": "3**5 + 100"})
    print(f"结果: {result}\n")

    # 4. Agent 通过 MCP Client 调工具
    print("=== Agent 集成 ===")
    import os; from dotenv import load_dotenv; load_dotenv()
    from openai import AsyncOpenAI

    client_api = AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    tools_desc = json.dumps(tools, ensure_ascii=False)
    prompt = f"你是 Agent。可用工具：{tools_desc}。严格按格式：Action: [工具名] / Action Input: [JSON参数]"

    response = await client_api.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "7 的 3 次方加上 50 等于多少？"},
        ],
    )
    reply = response.choices[0].message.content
    print(f"Agent: {reply}")

    # 如果 Agent 说要调工具，就通过 MCP 执行
    import re
    action = re.search(r"Action:\s*(\w+)", reply)
    if action:
        tool_name = action.group(1)
        input_match = re.search(r"Action Input:\s*(\{.*\})", reply, re.DOTALL)
        args = json.loads(input_match.group(1)) if input_match else {}
        obs = client.call_tool(tool_name, args)
        print(f"MCP 执行结果: {obs}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 三、验收标准

```bash
cd mcp-server && python test_mcp.py
```

- Agent 发现工具：`['calculator']`
- 直接调 `calculator("3**5+100")` → `343`
- Agent 通过 MCP 调 `calculator`

---

## 四、你现在的完整技术栈

```
Phase 1-2: API 封装层       ai-foundation/ llm-client/
Phase 3:   RAG 知识检索     rag-system/         ← 知识注入
Phase 4:   单 Agent 决策    single-agent/       ← 自主推理
Phase 5:   多 Agent 协作    multi-agent/        ← 分工合作
Phase 5b:  MCP 工具协议    mcp-server/         ← 标准化接口
```

MCP 不是新技术——是把你已经会的 JSON-RPC + 子进程通信 + ToolRegistry 套了一个标准协议壳。学了它你就懂了为什么"AI Agent 工具生态"是可能的。

---

## 五、Code Review 知识点（2026-05-08）

### 1. stderr 缓冲区死锁

`subprocess.Popen(stderr=PIPE)` 但不读 → 子进程 stderr 写满 64KB 缓冲区 → 阻塞 → 死锁。

**修法**：起 daemon 线程持续读 stderr，同时通过 `get_stderr()` 暴露日志用于排查。

### 2. `_send` 返回类型不一致

标注 `-> dict` 但 error 路径返回 `str`。`call_tool` 用 `isinstance(result, str)` 兜住了，`list_tools` 没兜 → 直接 `.get()` 炸 `AttributeError`。

**修法**：`list_tools` 加同样的 `isinstance` 守卫，error 时返回 `[]`。

### 3. `tools/call` 响应的 `content` 字段来源

```
server.handle_request  →  result: {"content": [{"type":"text","text":"5"}]}
_send 剥壳             →  response.get("result", {}) = {"content": [...]}
call_tool 提取         →  result.get("content", [])[0]["text"] = "5"
```

`content` 是 MCP 协议规定的字段，由 server 在 `result` 中返回，不是 client 凭空造的。

### 4. 相对路径陷阱

`MCPClient([sys.executable, "server.py"])` — `"server.py"` 相对的是 **CWD**（运行目录），不是脚本所在目录。从父目录运行找不到文件，子进程启动即死，`readline()` 返回 `""`, `json.loads("")` 崩。

**修法**：`Path(__file__).parent / "server.py"` 保证路径始终相对脚本文件。

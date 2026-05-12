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
            encoding='utf-8',  # MCP 协议规范要求 UTF-8
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

    def _send(self, method: str, params: dict | None = None) -> dict:
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

    def is_alive(self) -> bool:
        """健康检查：子进程是否还活着。"""
        return self.process.poll() is None

    def health_check(self) -> str:
        """快速验证 MCP 连接：发 tools/list 看能否正常响应。"""
        if not self.is_alive():
            return "进程已退出"
        try:
            result = self.list_tools()
            return f"OK ({len(result)} tools)" if isinstance(result, list) else f"异常: {result}"
        except Exception as e:
            return f"检查失败: {e}"

    def restart(self, server_cmd: list[str]):
        """重启 MCP 子进程。"""
        self.process.terminate()
        self.process = subprocess.Popen(
            server_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8',
        )

    def close(self):
        self.process.terminate()


async def main():
    # 1. 启动 MCP Server
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
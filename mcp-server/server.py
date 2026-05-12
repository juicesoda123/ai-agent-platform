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
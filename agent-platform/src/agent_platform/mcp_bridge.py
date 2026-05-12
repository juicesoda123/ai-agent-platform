"""MCP 工具桥接 —— 把社区 MCP Server 的工具注入 ToolRegistry。

支持两种 MCP Server：
  1. Python MCP (uvx) — 优先，零依赖
  2. Node.js MCP (npx) — 备选
"""

import json, sys, shutil
from pathlib import Path
from pydantic import BaseModel, Field, create_model

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-server"))
from test_mcp import MCPClient


def _find_cmd(candidates: list[str]) -> str | None:
    """在 PATH 中找第一个可用的命令。"""
    for c in candidates:
        if shutil.which(c):
            return c
    return None


class MCPBridge:
    """连接 MCP Server → 注入 ToolRegistry。"""

    def __init__(self, server_cmd: list[str]):
        self.client = MCPClient(server_cmd)
        self.tools = self.client.list_tools()

    def register_all(self, registry) -> None:
        """把 MCP Server 的全部工具注册到 ToolRegistry。"""
        for tool in self.tools:
            name = tool["name"]
            description = tool.get("description", "")

            input_model = create_model(
                f"MCP_{name}",
                __base__=BaseModel,
                path=(str, Field(default="", description="文件路径")),
                pattern=(str, Field(default="", description="搜索模式")),
                content=(str, Field(default="", description="文件内容")),
                edits=(str, Field(default="[]", description="编辑操作")),
            )
            def make_func(tn):
                def _call(**kwargs):
                    args = {k: v for k, v in kwargs.items() if v not in ("", "[]", None)}
                    result = self.client.call_tool(tn, args)
                    return result if isinstance(result, str) else str(result)
                return _call

            registry.register(name, description, make_func(name), input_model)

    def health_check(self) -> str:
        if not self.client.is_alive():
            return "DOWN"
        return self.client.health_check()

    def close(self):
        self.client.close()


# ============================================================
# 自动发现可用的 MCP 运行时（npx 或 uvx）
# ============================================================

_npx = _find_cmd(["npx.cmd", "npx"])
_uvx = _find_cmd(["uvx.exe", "uvx"])

# MCP 服务器列表：名称 → (运行时, 包名, 参数)
MCP_SERVERS = []

# Filesystem — Python 版优先（不需要 Node.js）
if _uvx:
    MCP_SERVERS.append(("filesystem", [_uvx, "mcp-server-filesystem", str(Path(__file__).parent.parent.parent.parent)]))
elif _npx:
    MCP_SERVERS.append(("filesystem", [_npx, "-y", "@modelcontextprotocol/server-filesystem", str(Path(__file__).parent.parent.parent.parent)]))

# GitHub
if _npx:
    MCP_SERVERS.append(("github", [_npx, "-y", "@modelcontextprotocol/server-github"]))

# Sequential Thinking
if _npx:
    MCP_SERVERS.append(("sequential", [_npx, "-y", "@modelcontextprotocol/server-sequential-thinking"]))


def register_mcp_servers(registry) -> int:
    """自动注册所有可用的 MCP 服务器。返回成功注册的数量。"""
    count = 0
    for name, cmd in MCP_SERVERS:
        try:
            MCPBridge(cmd).register_all(registry)
            count += 1
        except Exception:
            pass
    return count

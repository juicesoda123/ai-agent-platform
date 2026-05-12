"""MCP 工具桥接 —— 把社区 MCP Server 的工具注入 ToolRegistry。

用法:
    bridge = MCPBridge(["npx", "-y", "@modelcontextprotocol/server-filesystem", "D:/path"])
    registry = ToolRegistry()
    bridge.register_all(registry)
    # 现在 registry 里有了 read_file / list_directory / search_files ...
"""

import json
import sys
from pathlib import Path
from pydantic import BaseModel, Field, create_model

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-server"))
from test_mcp import MCPClient


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

            # 创建一个接受任意参数的 Pydantic 模型
            input_model = create_model(
                f"MCP_{name}",
                __base__=BaseModel,
                path=(str, Field(default="", description="文件路径")),
                pattern=(str, Field(default="", description="搜索模式")),
                content=(str, Field(default="", description="文件内容")),
                edits=(str, Field(default="[]", description="编辑操作")),
            )
            # 用闭包绑定 tool name
            def make_func(tn):
                def _call(**kwargs):
                    # 过滤掉默认空值的参数
                    args = {k: v for k, v in kwargs.items() if v != "" and v != "[]"}
                    result = self.client.call_tool(tn, args)
                    if isinstance(result, str):
                        return result
                    return str(result)
                return _call

            registry.register(name, description, make_func(name), input_model)

    def health_check(self) -> str:
        """检查 MCP 连接健康状态。"""
        if not self.client.is_alive():
            return "DOWN — 进程已退出"
        return self.client.health_check()

    def close(self):
        self.client.close()

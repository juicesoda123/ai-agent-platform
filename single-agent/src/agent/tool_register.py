"""Tool Registry —— 自动化工具管理。

教学点：
  1. Pydantic → JSON Schema：自动生成工具参数定义
  2. Tool 元数据：name / description / func / schema 打包在一起
  3. 动态 System Prompt：工具变了 Prompt 自动更新
"""

from typing import Callable
from pydantic import BaseModel, create_model, Field

class ToolInfo:
    """工具信息，包括函数和参数定义。"""
    def __init__(self, name: str, description: str, func: Callable, input_model: BaseModel):
        self.name = name
        self.description = description
        self.func = func
        self.input_model = input_model

    def to_dict(self) -> dict:
        """生成给LLM看的工具description"""

        schema = self.input_model.model_json_schema()
        params = schema.get("properties", {})
        para_desc = ",".join(f"{k}: {v.get('type', '?')}" for k, v in params.items())
        return {
            "name": self.name,
            "description": self.description,
            "parameters": para_desc,
        }    
    
class ToolRegistry:
    """工具注册中心--加工具、查工具、生成Prompt"""

    def __init__(self):
        self._tools : dict[str, ToolInfo] = {}
    
    def register(
        self,
        name: str,
        description: str,
        func: Callable,
        input_model: type[BaseModel],
    ) -> None:
        """register a tool"""
        self._tools[name] = ToolInfo(name, description, func, input_model)

    def get(self, name: str) -> ToolInfo:
        """get tool info by name"""
        return self._tools.get(name)
    
    def call(self, name: str, **kwargs) -> str:
        """按名称调用工具"""
        tool =self._tools.get(name)
        if not tool:
            return f"工具 '{name}' 不存在。可用：{list(self._tools.keys())}"
        try: 
            params = tool.input_model(**kwargs)
            return str(tool.func(**params.model_dump()))
        except Exception as e:
            return f"调用工具 '{name}' 时出错: {e}"
        
    def list_tools(self) -> list[dict]:
        """列出所有可用工具"""
        return [tool.to_dict() for tool in self._tools.values()]
    
    def generate_system_prompt(self, base_prompt: str) -> str:
        """动态生成 System Prompt，工具列表自动更新"""
        tool_list = "\n".join(
            f"- {tool.name}: {tool.description} (参数: {tool.to_dict()['parameters']})"
            for tool in self._tools.values()
        )
        return f"""{base_prompt}

可用工具：
{tool_list}

规则：
1. 每次只能调用一个工具
2. 严格使用 JSON 格式：Action Input: {{"参数名": "值"}}
3. 工具结果以 Observation 返回，拿到足够信息后给出 Final Answer
4. 不要编造信息"""
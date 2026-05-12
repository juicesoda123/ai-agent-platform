import json
from typing import Callable
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，例如 '3 + 4 * 2'")

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, ge=1, le=50, description="返回结果数量,1-50")

class Tool:
    """一个工具 = 名字 + 描述 + 参数 Schema + 执行函数。"""

    def __init__ (self, name: str, description: str, input_model: type[BaseModel], func: Callable):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.func = func

    def to_openai_schema(self) -> dict:
        """转成 OpenAI Function Calling 需要的格式。"""
        schema = self.input_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            }
        }
    
    def run (self, args_json: str) -> str:
        """执行工具：JSON 参数 → 调函数 → 返回字符串结果。"""
        params = self.input_model.model_validate_json(args_json)
        return str(self.func(**params.model_dump()))
    
# ——— 具体的工具函数 ———
def calculator(expression: str) -> str:
    """安全的计算器——只做简单数学，不 eval 任意代码。"""
    allowed = set("0123456789+-*/().%^ ")
    if not all(c in allowed for c in expression):
        return "错误：表达式包含不安全字符"
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"计算错误: {e}"    

def search(query: str, max_results: int = 10) -> str:
    """模拟搜索——暂时返回假数据，Phase 3 接真正的搜索 API。"""
    return f"搜索结果（模拟）: 关于'{query}'，找到 {max_results} 条相关信息..."

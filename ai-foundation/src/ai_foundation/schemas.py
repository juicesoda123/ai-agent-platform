"""Agent 工具的数据模型 —— Pydantic 实战。

教学点：
  1. BaseModel：定义数据结构的"模板"
  2. Field()：给字段加约束和描述
  3. 嵌套模型：一个模型包含另一个模型
  4. model_dump()：把模型转成 dict（给 API 用）
"""

from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, ge=1, le=50, description="返回结果数量,1-50")
    language: str = Field(default="zh", description="搜索语言")

class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，例如 '3 + 4 * 2'")

class ToolDefinition(BaseModel):
    name: str = Field(description="工具名称，唯一标识")
    description: str = Field(description="工具功能描述")
    input_schema: type[BaseModel] = Field(description="输入参数的 Pydantic 模型")


# ——— 工具调用结果 ———
class ToolCallResult(BaseModel):
    """工具执行后的返回结果。"""

    tool_name: str
    success: bool
    data: str
    error: str | None = None
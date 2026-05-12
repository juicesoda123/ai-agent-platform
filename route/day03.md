# Day 03 — Pydantic 数据验证 / 配置管理 / 嵌套模型

> Phase 1：Python 工程补强  |  预计用时：45-60 分钟  |  2026-05-04

---

## 今日目标

1. 理解 Pydantic BaseModel——不只是读配置，是数据验证框架
2. 学会 Field validator——数据进来时自动校验/转换
3. 学会嵌套模型——复杂 JSON 结构怎么用 Pydantic 表达
4. 产出：Tool 定义模型 + 配置模型增强

---

## 一、概念对齐：Pydantic 是什么

Pydantic = **数据验证 + 类型转换 + JSON Schema 生成**。在 AI Agent 里它是最重要的基础设施之一——Function Calling 的 tool schema 全靠它生成。

```
你的代码                     Pydantic                    LLM API
定义 class            →     自动生成 JSON Schema    →   Function Calling
ToolInput(BaseModel):        {"type":"object",            tool definition
    query: str               "properties":{"query":
    limit: int               {"type":"string"}}}
```

---

## 二、阅读代码（10 分钟）

### 文件 1：重读 `config.py`，这次关注 Pydantic 机制

```python
class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", ...)

    deepseek_api_key: str                          # 从 .env 加载
    deepseek_base_url: str = "https://api.deepseek.com"  # 有默认值
```

关键问题：
- `.env` 里的 `DEEPSEEK_API_KEY` 是怎么变成 `config.deepseek_api_key` 的？

- 如果 `.env` 里没有 `DEEPSEEK_API_KEY`，实例化 `LLMConfig()` 会怎样？

  答案：如果你 .env 里没配 DEEPSEEK_API_KEY，实例化 LLMConfig() 的那一刻就报 ValidationError——不是用到 API
    的时候才炸，是程序启动就炸。

    这就是 Pydantic 比 os.getenv() 高明的地方——把错误从运行时提前到启动时。你 ML
    里写过训练脚本就知道，跑了半小时才发现某个超参没配，那感觉有多崩溃。Pydantic 让你代码一启动就知道"缺了什么"，不浪费一分钟算力。

    ▎ Fail fast 原则：能早炸绝不晚炸。这叫底线思维。

### 文件 2：看看 OpenAI SDK 怎么用 Pydantic

不需要读源码，理解这个模式就够了：

```python
from openai.types.chat import ChatCompletion

# OpenAI SDK 的响应对象全是 Pydantic BaseModel
response = await client.chat.completions.create(...)
# response 是 ChatCompletion 类型，所有字段都有类型提示
# response.choices[0].message.content  ← IDE 自动补全
```

---

## 三、动手实战（35 分钟）

### 任务 1：创建 Tool 定义模型

在 `ai-foundation/src/ai_foundation/` 下新建 `schemas.py`，用 Pydantic 定义 Agent 工具的输入输出结构。

```python
"""Agent 工具的数据模型 —— Pydantic 实战。

教学点：
  1. BaseModel：定义数据结构的"模板"
  2. Field()：给字段加约束和描述
  3. 嵌套模型：一个模型包含另一个模型
  4. model_dump()：把模型转成 dict（给 API 用）
"""

from pydantic import BaseModel, Field


# ——— 一个搜索工具的输入 ———
class SearchInput(BaseModel):
    """搜索工具输入参数。"""

    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=10, ge=1, le=50, description="返回结果数量，1-50")
    language: str = Field(default="zh", description="搜索语言")


# ——— 一个计算器工具的输入 ———
class CalculatorInput(BaseModel):
    """计算器工具输入参数。"""

    expression: str = Field(description="数学表达式，例如 '3 + 4 * 2'")


# ——— 工具的统一包装 ———
class ToolDefinition(BaseModel):
    """定义一个工具——给 Agent 注册用。"""

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
```

### 任务 2：写验证脚本

在 `examples/` 下新建 `test_schemas.py`：

```python
"""验证 Pydantic 数据模型——自动校验 + JSON Schema 生成。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.schemas import (
    SearchInput,
    CalculatorInput,
    ToolDefinition,
    ToolCallResult,
)


def main() -> None:
    # 1. 正常创建——数据合法
    search = SearchInput(query="Python Pydantic 教程", max_results=5)
    print(f"搜索: query={search.query}, max={search.max_results}")

    # 2. 数据不合法——max_results 超出范围会怎样？
    try:
        bad = SearchInput(query="test", max_results=100)
        print(f"异常没触发？{bad}")
    except Exception as e:
        print(f"校验失败（预期内）: {e}")

    # 3. model_dump()——转成 dict 给 API 用
    calc = CalculatorInput(expression="3 + 4 * 2")
    print(f"\nCalculatorInput → dict: {calc.model_dump()}")

    # 4. 嵌套使用——ToolDefinition 包含另一个模型
    tool = ToolDefinition(
        name="search",
        description="搜索互联网获取最新信息",
        input_schema=SearchInput,
    )
    print(f"\n工具名: {tool.name}")
    print(f"输入类型: {tool.input_schema.__name__}")

    # 5. 尝试用 input_schema 创建实例（Agent 里的实际用法）
    sample_input = tool.input_schema(query="今天天气怎么样")
    print(f"动态创建输入: {sample_input.model_dump()}")

    # 6. ToolCallResult——包含可选字段
    ok = ToolCallResult(tool_name="search", success=True, data="找到 5 条结果")
    fail = ToolCallResult(tool_name="search", success=False, data="", error="连接超时")
    print(f"\n成功: {ok}")
    print(f"失败: {fail}")


if __name__ == "__main__":
    main()
```

### 任务 3：改造 `LLMConfig`，添加字段验证

在 `config.py` 的 `LLMConfig` 里加一个 validator，确保 API Key 不为空：

```python
from pydantic import field_validator  # 加在 config.py 顶部 import

class LLMConfig(BaseSettings):
    # ... 原有字段不变 ...

    @field_validator("deepseek_api_key")
    @classmethod
    def check_api_key(cls, v: str) -> str:
        """校验 API Key 不为空且以 sk- 开头。"""
        if not v or not v.startswith("sk-"):
            raise ValueError("DEEPSEEK_API_KEY 不能为空，且必须以 sk- 开头")
        return v
```

---

## 四、验收标准

运行 `test_schemas.py`：

```bash
cd ai-foundation && python examples/test_schemas.py
```

预期输出：

```
搜索: query=Python Pydantic 教程, max=5
校验失败（预期内）: ...less than or equal to 50...
CalculatorInput → dict: {'expression': '3 + 4 * 2'}

工具名: search
输入类型: SearchInput
动态创建输入: {'query': '今天天气怎么样', 'max_results': 10, 'language': 'zh'}

成功: ToolCallResult(tool_name='search', success=True, ...)
失败: ToolCallResult(tool_name='search', success=False, ...)
```

---

## 五、概念速查

### BaseModel vs dataclass

| | dataclass | pydantic BaseModel |
|------|-----------|-------------------|
| 数据校验 | ❌ 无，传错类型照样跑 | ✅ 自动校验，类型错当场报 |
| JSON 序列化 | ❌ 需要手动写 | ✅ `.model_dump()` 一键转 dict |
| JSON Schema | ❌ 无 | ✅ `.model_json_schema()` |
| AI 项目里用在哪 | 内部简单数据（Message） | 配置/Tool Schema/API 响应 |

**选型原则**：要和外部系统交互的数据 → Pydantic。只在内部传递的简单结构 → dataclass。

# Day 06 — 综合实战：多模型工厂 + Phase 1 串联

> Phase 1：Python 工程补强  |  预计用时：45-60 分钟  |  2026-05-05

---

## 今日目标

1. 实现 `OpenAIClient`——和 DeepSeekClient 同接口，换一个 API
2. 实现工厂函数 `create_llm_client()`——根据配置自动选模型
3. 感受多态的真正威力——改一行代码换模型，其他全不动
4. 产出：一个脚本同时调 DeepSeek 和 OpenAI，零重复代码

---

## 一、你要写的两个东西

### 任务 1：`OpenAIClient`（10 分钟）

在 `src/ai_foundation/llm/` 下新建 `openai_impl.py`：

```python
"""OpenAI LLM 客户端 —— 和 DeepSeekClient 共用同一个父类。"""

import asyncio
from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from ai_foundation.llm.base import BaseLLMClient, LLMResponse, Message


class OpenAIClient(BaseLLMClient):
    """OpenAI API 客户端。代码结构和 DeepSeekClient 几乎一样。"""

    MAX_RETRIES = 3

    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        super().__init__(model, api_key, base_url)
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def _complete(self, messages: list[Message]) -> LLMResponse:
        message_dicts = [msg.to_dict() for msg in messages]
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=message_dicts,
                )
                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=self.model,
                    tokens_used=response.usage.total_tokens,
                )
            except APIConnectionError as e:
                last_error = e
                print(f"  [OpenAI 网络错误] 重试 {attempt+1}/{self.MAX_RETRIES}")
            except APIStatusError as e:
                if e.status_code < 500:
                    raise
                last_error = e
                print(f"  [OpenAI {e.status_code}] 重试 {attempt+1}/{self.MAX_RETRIES}")

            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)

        raise last_error
```

**你会发现**——这个类除了类名，和 `DeepSeekClient` 几乎一模一样。这就是"模板方法模式"的代价：每种 API 都要写一遍 `_complete`，但好处是调用方完全不用改。

> 后面 Phase 4 我们会用依赖注入把重试逻辑抽到基类里，现在先不动——先让你感受"重复代码"的痛点，才能理解"抽基类"的价值。

### 任务 2：工厂函数（15 分钟）

在 `src/ai_foundation/llm/` 下新建 `factory.py`：

```python
"""LLM 客户端工厂 —— 根据配置自动创建对应的客户端。

教学点：
  1. 工厂模式：把"创建哪个类"的决策集中到一个地方
  2. 多态：返回类型是 BaseLLMClient，调用方不关心具体实现
"""

from ai_foundation.config import LLMConfig
from ai_foundation.llm.base import BaseLLMClient
from ai_foundation.llm.deepseek_impl import DeepSeekClient
from ai_foundation.llm.openai_impl import OpenAIClient


def create_llm_client(config: LLMConfig) -> BaseLLMClient:
    """根据配置创建 LLM 客户端。优先使用 DeepSeek，其次 OpenAI。"""
    if config.deepseek_api_key:
        return DeepSeekClient(
            model="deepseek-chat",
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
        )
    elif config.has_openai:
        return OpenAIClient(
            model="gpt-4o",
            api_key=config.openai_api_key,
            base_url="https://api.openai.com/v1",
        )
    else:
        raise ValueError("没有可用的 API Key，请配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
```

### 任务 3：串联验证（15 分钟）

在 `examples/` 下新建 `test_factory.py`：

```python
"""验证工厂函数 + 多态——同一段调用代码，跑两个不同的模型。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.factory import create_llm_client
from ai_foundation.llm.base import BaseLLMClient


async def ask(client: BaseLLMClient, question: str) -> None:
    """这个函数不关心 client 是 DeepSeek 还是 OpenAI——多态。"""
    r = await client.chat(user_message=question)
    print(f"  [{r.model}] {r.content[:60]}...  ({r.tokens_used} tokens)")


async def main() -> None:
    config = LLMConfig()

    # 一行代码决定用哪个模型——其他代码完全不用改
    client = create_llm_client(config)
    print(f"使用模型: {type(client).__name__}\n")

    questions = [
        "什么是 Python 装饰器？一句话。",
        "什么是设计模式中的工厂模式？一句话。",
    ]

    for q in questions:
        await ask(client, q)

    # 多态验证
    print(f"\nisinstance(client, BaseLLMClient): {isinstance(client, BaseLLMClient)}")


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
cd ai-foundation && python examples/test_factory.py
```

---

## 二、验收标准

预期输出：

```
使用模型: DeepSeekClient

  [deepseek-chat] 装饰器是...  (XX tokens)
  [deepseek-chat] 工厂模式是...  (XX tokens)

isinstance(client, BaseLLMClient): True
```

---

## 三、Phase 1 五天回顾——你写了什么

```
ai-foundation/
├── src/ai_foundation/
│   ├── config.py           ← Pydantic Settings + field_validator
│   ├── schemas.py           ← Pydantic BaseModel 工具定义
│   └── llm/
│       ├── base.py          ← 抽象基类 + Message/LLMResponse
│       ├── deepseek_impl.py ← DeepSeek 客户端 + 指数退避重试
│       ├── openai_impl.py   ← OpenAI 客户端（今天新增）
│       ├── factory.py       ← 工厂函数（今天新增）
│       └── __init__.py
├── examples/
│   ├── hello_agent.py           ← D1: 第一个 API 调用
│   ├── my_typing_practice.py    ← D1: 类型注解练习
│   ├── test_deepseek_client.py  ← D2: 继承多态验证
│   ├── test_schemas.py          ← D3: Pydantic 数据验证
│   ├── test_async_concurrent.py ← D4: 串行 vs 并发
│   ├── test_retry.py            ← D5: 重试机制
│   └── test_factory.py          ← D6: 工厂 + 多模型串联
└── .env / .gitignore / requirements.txt
```

六天前你还在问"什么是类型注解"，六天后你手里是一个能自动选择模型、带重试、带配置校验、支持多模型切换的 LLM 客户端库。

> 今天最好的表现，是明天最低的要求。D6 是 Phase 1 最后一战——写完它，D7 就是代码审查 + 进阶方向。

# Day 02 — OOP 核心：继承 / 多态 / 抽象基类

> Phase 1：Python 工程补强  |  预计用时：45-60 分钟  |  2026-05-04

---

## 今日目标

1. 理解继承——子类怎么复用父类的代码
2. 理解多态——同一个接口，不同实现可以互相替换
3. 理解抽象基类——怎么用 ABC 约束子类"你必须实现这些方法"
4. 产出：`DeepSeekClient` — 继承 `BaseLLMClient` 的完整实现

---

## 一、概念对齐（5 分钟，先看再动手）

### 继承（Inheritance）

```
父类（基类）：定义了"通用能力"——比如"所有 LLM 客户端都需要 api_key"
子类（派生类）：继承父类，加上"特有能力"——比如 DeepSeek 的 base_url

关系：DeepSeekClient is-a BaseLLMClient
      一个 DeepSeek 客户端 "是一个" LLM 客户端
```

```python
class Animal:                    # 父类
    def __init__(self, name: str):
        self.name = name

    def speak(self) -> str:      # 父类方法
        return "..."

class Dog(Animal):               # 子类继承 Animal
    def speak(self) -> str:      # 重写（override）父类方法
        return "Woof!"

class Cat(Animal):               # 另一个子类
    def speak(self) -> str:
        return "Meow!"
```

### 多态（Polymorphism）

> 同一个接口，不同的实现。调用方不关心具体是哪个子类。

```python
def make_speak(animal: Animal) -> None:
    print(animal.speak())        # 不管传 Dog 还是 Cat，都能正确调用

make_speak(Dog("旺财"))  # Woof!
make_speak(Cat("咪咪"))  # Meow!
```

**在 AI Agent 里**：你的代码只依赖 `BaseLLMClient`，换模型时换个子类就行，调用方一行不改。

### 抽象基类（Abstract Base Class）

> "我不管你怎么实现，但你必须有这些方法。"——给子类定规矩。

```python
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):            # 继承 ABC = 这是抽象基类
    @abstractmethod
    async def _complete(self, ...):  # 子类必须实现，否则实例化时报错
        ...
```

---

## 二、阅读代码（10 分钟）

### 文件 1：重新精读 `ai-foundation/src/ai_foundation/llm/base.py`

这次带着这三个问题读：

1. `BaseLLMClient.__init__` 里存了哪些属性？子类能不能直接用 `self.model`？
2. `chat()` 方法为什么不是抽象的？子类需要重写它吗？
3. 如果写一个 `class DeepSeekClient(BaseLLMClient): pass` 然后实例化，会报什么错？

### 文件 2：看一下 OpenAI Python SDK 是怎么用继承的

不需要你读源码，看这个调用就够了：

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=config.deepseek_api_key,
    base_url=config.deepseek_base_url,  # ← 换 URL 就换模型
)
```

OpenAI SDK 内部也是继承体系——`AsyncOpenAI` 继承自某个基类，封装了 HTTP 连接、重试、流式等通用能力。你接下来写的 `DeepSeekClient` 也是同样的思路。

---

## 三、动手实战（30 分钟）

### 任务：实现 `DeepSeekClient`

在 `ai-foundation/src/ai_foundation/llm/` 下新建 `deepseek_impl.py`，写一个继承 `BaseLLMClient` 的 DeepSeek 客户端。

**要求：**

1. 继承 `BaseLLMClient`
2. 实现 `_complete()` 方法——调用 DeepSeek API
3. `__init__` 里创建 `AsyncOpenAI` 实例（复用 OpenAI SDK）
4. 类型注解完整

**代码骨架（补全 TODO 部分）：**

```python
"""DeepSeek LLM 客户端 —— 继承 BaseLLMClient，对接 DeepSeek API。

教学点：
  1. 继承：DeepSeekClient(BaseLLMClient) 复用父类的 chat() 方法
  2. 多态：用 BaseLLMClient 类型接收，不关心底层是 DeepSeek 还是 OpenAI
  3. super()：调用父类的 __init__，让父类初始化通用属性
"""

from openai import AsyncOpenAI

from ai_foundation.llm.base import BaseLLMClient, LLMResponse, Message


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API 客户端。"""

    # TODO: 实现 __init__
    # 提示：用 super().__init__(...) 调用父类构造函数
    # 提示：创建 self._client = AsyncOpenAI(api_key=..., base_url=...)

    # TODO: 实现 _complete
    # 提示：调用 self._client.chat.completions.create(model=self.model, messages=...)
    # 提示：从 response 中提取 content 和 usage.total_tokens
    # 提示：返回 LLMResponse(content=..., model=..., tokens_used=...)
```

**参考：** 你昨天写的 `hello_agent.py` 里已经有调用 DeepSeek 的完整代码，直接搬过来改。

### 写完后的验证脚本

在 `examples/` 下新建 `test_deepseek_client.py`：

```python
"""验证 DeepSeekClient 继承和多态。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.deepseek_impl import DeepSeekClient
from ai_foundation.llm.base import BaseLLMClient  # 多态验证用


async def main() -> None:
    config = LLMConfig()

    # 1. 实例化子类
    client: BaseLLMClient = DeepSeekClient(  # ← 类型标注为 BaseLLMClient
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
    )

    # 2. 调用父类提供的 chat() 方法（多态）
    response = await client.chat(
        user_message="用一句话解释什么是 Python 的 super()。",
        system_prompt="你是 Python 教学助手，用中文回答。",
    )

    print(f"模型: {response.model}")
    print(f"回复: {response.content}")
    print(f"Tokens: {response.tokens_used}")

    # 3. 验证多态：isinstance 检查
    print(f"\n是 DeepSeekClient 吗？ {isinstance(client, DeepSeekClient)}")
    print(f"是 BaseLLMClient 吗？ {isinstance(client, BaseLLMClient)}")


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
cd ai-foundation && python examples/test_deepseek_client.py
```

---

## 四、验收标准

运行 `test_deepseek_client.py`，预期输出类似：

```
模型: deepseek-chat
回复: super() 是用来调用父类方法的...
Tokens: 45

是 DeepSeekClient 吗？ True
是 BaseLLMClient 吗？ True
```

两个 `True` 是关键——证明你的 `DeepSeekClient` 既是子类也是父类类型，**多态成立**。

---

## 五、概念速查：super() 是什么

```python
class Parent:
    def __init__(self, name: str):
        self.name = name

class Child(Parent):
    def __init__(self, name: str, age: int):
        super().__init__(name)   # ← 调用 Parent.__init__，让父类初始化 name
        self.age = age           # ← 自己只处理新增的属性
```

> `super()` = "我的父类"。`super().__init__()` = "让父类先初始化它负责的那些字段，我再初始化我新增的"。不写 `super().__init__()` 父类的属性就不会被初始化，后面用 `self.name` 就炸。

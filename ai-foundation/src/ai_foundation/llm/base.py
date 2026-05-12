"""LLM 客户端抽象基类。

教学点 —— OOP 三大支柱在这里全出现：
  1. 封装：把 API Key、base_url、client 实例包在类里
  2. 继承：DeepSeekClient 继承 BaseLLMClient
  3. 多态：调用的地方只依赖 BaseLLMClient，不关心具体是哪个模型

还有：
  - 抽象方法 (@abstractmethod)：子类必须实现，不实现就报错
  - 类型注解：每个参数/返回值都有类型，IDE 能自动补全
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ——— 数据结构：先定义"消息长什么样" ———
# dataclass 是 Python 的轻量数据结构，比 dict 多了类型安全
# 你写 C#/Java 的话，这就相当于 POCO/POJO

@dataclass
class Message:
    """一条对话消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        """转成 OpenAI 兼容的 dict 格式。"""
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """LLM 返回的统一结构。屏蔽不同 API 的差异。"""

    content: str
    model: str
    tokens_used: int  # 消耗的 token 数，用于成本核算


# ——— 抽象基类：定义"一个 LLM 客户端必须能做什么" ———

class BaseLLMClient(ABC):
    """所有 LLM 客户端的统一接口。

    子类只需要实现 _complete 这一个方法，其他能力（重试、日志）由基类提供。
    这就是 OOP 的"模板方法模式"——基类定流程，子类填细节。
    """

    def __init__(self, model: str, api_key: str, base_url: str) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    # 抽象方法：子类必须实现
    @abstractmethod
    async def _complete(self, messages: list[Message]) -> LLMResponse:
        """调用 LLM API，返回统一响应。子类实现。"""
        ...

    # 普通方法：子类直接继承，不用重写
    async def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """发送一条用户消息，返回 LLM 回复。

        这是给外部调用的"高层接口"——调用者不需要知道底层 API 细节。
        """
        messages: list[Message] = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        messages.append(Message(role="user", content=user_message))
        return await self._complete(messages)

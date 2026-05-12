"""Phase 1 第一个可运行示例 —— 验证整个骨架能跑通。

运行方式（在 ai-foundation 目录下）：
  python examples/hello_agent.py
"""

import asyncio
import sys
from pathlib import Path

# 把 src 目录加到 Python 搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from openai import AsyncOpenAI


async def main() -> None:
    """最简单的 LLM 调用 —— 验证 API Key 和网络都正常。"""
    config = LLMConfig()  # Pydantic 自动从 .env 加载

    # 用 DeepSeek API（兼容 OpenAI SDK）
    client = AsyncOpenAI(
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
    )

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是 AI Agent 学习助手，用中文回答。"},
            {"role": "user", "content": "什么是 Python 类型注解？用一句话回答。"},
        ],
    )

    content = response.choices[0].message.content
    tokens = response.usage.total_tokens
    print(f"回复: {content}")
    print(f"Token 消耗: {tokens}")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_foundation.config import LLMConfig
from ai_foundation.llm.deepseek_impl import DeepSeekClient

async def main() -> None:
    config = LLMConfig()
    client = DeepSeekClient(
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
    )
    r = await client.chat(user_message="说一个数字。")
    print(f"LLM 回复: {r.content}")

    bad_client = DeepSeekClient(
        model="deepseek-chat",
        api_key=config.deepseek_api_key,
        base_url="https://api.deepseek-typo-wrong.com",  # 故意写错的 URL
    )
    try:
        r = await bad_client.chat(user_message="Hello")
        print(f"成功: {r.content}")
    except Exception as e:
        print(f"\n重试全部失败后抛出: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
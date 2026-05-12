import os
from openai import AsyncOpenAI

def create_client() -> AsyncOpenAI:
    if os.getenv("DEEPSEEK_API_KEY"):
        return AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com"),
        )
    elif os.getenv("OPENAI_API_KEY"):
        return AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://api.openai.com/v1",
        )
    raise ValueError("未找到 DEEPSEEK_API_KEY or OPENAI_API_KEY")
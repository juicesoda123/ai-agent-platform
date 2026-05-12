from ai_foundation.config import LLMConfig
from ai_foundation.llm.base import BaseLLMClient
from ai_foundation.llm.deepseek_impl import DeepSeekClient
from ai_foundation.llm.openai_impl import OpenAIClient

def create_llm_client(config: LLMConfig) -> BaseLLMClient:
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
        raise ValueError("no available API KEY,请配置")
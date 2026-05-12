"""配置管理 —— 用 Pydantic Settings 从环境变量/.env 加载配置。

教学点：
  1. 类型注解 (Type Hints) — 每个字段后面 : str 就是类型注解
  2. Pydantic BaseSettings — 自动从 .env 读配置，类型校验
  3. 为什么不用 os.getenv() 裸调？因为 Pydantic 帮你校验"必填字段缺了没"
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """LLM 相关配置。字段名自动匹配环境变量（不区分大小写）。"""
    deepseek_api_key: str  # ← 类型注解：告诉 Python 这个字段必须是 str
    deepseek_base_url: str = "https://api.deepseek.com"
    openai_api_key: str = ""  # = "" 表示可选，有默认值

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 中未定义的字段
    )
    
    @field_validator("deepseek_api_key")
    @classmethod
    def check_api_key(cls, v: str) -> str:
        """校验 API Key 不为空且以 sk- 开头。"""
        if not v or not v.startswith("sk-"):
            raise ValueError("DEEPSEEK_API_KEY 不能为空，且必须以 sk- 开头")
        return v


    @property
    def has_openai(self) -> bool:  # ← 返回类型注解
        """检查是否配置了 OpenAI API Key。"""
        return bool(self.openai_api_key)

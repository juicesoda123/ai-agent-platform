def count_tokens(text: str) -> int:
    """估算文本的 token 数（中文约 1 个字符 = 1 token，粗暴按 1/3 折算）。"""
    return len(text) // 3
print(count_tokens("你好世界"))        # 预期：1
print(count_tokens("Hello World"))     # 预期：3
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    data: str
    error: str | None = None  # 默认 None，成功时不需要填
ok = ToolResult(success=True, data="操作成功")
fail = ToolResult(success=False, data="", error="连接超时")
print(ok)
print(fail)
from dotenv import load_dotenv
import os

load_dotenv()  # 把 .env 的内容加载到环境变量

api_key = os.getenv("DEEPSEEK_API_KEY", "")
if api_key:
    print(f"Key 前 8 位: {api_key[:8]}...")
else:
    print("未找到 DEEPSEEK_API_KEY")
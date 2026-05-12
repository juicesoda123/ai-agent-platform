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
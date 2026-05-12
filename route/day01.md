# Day 01 — 环境搭建 + 类型注解 + 项目结构

> Phase 1：Python 工程补强  |  预计用时：30-40 分钟  |  2026-05-04

---

## 今日目标

1. 理解 Python 类型注解的写法和应用场景
2. 学会用 `@dataclass` 定义类型安全的数据结构
3. 理解 Pydantic 怎么从 `.env` 自动加载配置
4. 认识一个标准化 Python 项目的目录结构

---

## 一、阅读代码（15 分钟）

**按顺序打开以下三个文件，读代码 + 读注释：**

### 文件 1：`ai-foundation/src/ai_foundation/config.py`

| 关注点 | 说明 |
|--------|------|
| `class LLMConfig(BaseSettings)` | Pydantic 的 `BaseSettings` 会自动从 `.env` 文件加载同名环境变量 |
| `deepseek_api_key: str` | 这就是**类型注解**——`冒号 + 类型`，告诉 Python 这个字段必须是一个字符串 |
| `deepseek_base_url: str = "https://..."` | 有默认值的类型注解，表示可选字段 |
| `model_config` | Pydantic 的配置字典，指定 `.env` 文件路径 |
| `@property` | 把一个方法变成"像属性一样调用"，`config.has_openai` 不需要加括号 |

### 文件 2：`ai-foundation/src/ai_foundation/llm/base.py`

| 关注点 | 说明 |
|--------|------|
| `@dataclass` | 装饰器，自动给类生成 `__init__`、`__repr__` 等方法。适合做"数据结构" |
| `Message` dataclass | 定义一条消息长什么样——`role` + `content` |
| `LLMResponse` dataclass | 定义 LLM 返回结果长什么样——统一不同 API 的差异 |
| `class BaseLLMClient(ABC)` | 继承 `ABC` = 这是一个**抽象基类**，不能直接实例化 |
| `@abstractmethod` | 子类**必须实现**这个方法，否则报错 |
| `async def _complete(...)` | `async` = 异步方法，调用 LLM API 时不阻塞整个程序 |
| `-> LLMResponse` | 返回值类型注解，表示这个方法返回 `LLMResponse` 对象 |
| `str \| None` | 联合类型——这个参数可以是 `str` 或 `None` |

### 文件 3：`ai-foundation/examples/hello_agent.py`

| 关注点 | 说明 |
|--------|------|
| `LLMConfig()` | 实例化配置类，Pydantic 自动从 `.env` 加载 |
| `AsyncOpenAI(...)` | OpenAI 兼容客户端，传入 DeepSeek 的地址就能调用 DeepSeek |
| `await client.chat.completions.create(...)` | `await` = 等待异步调用完成 |
| `response.choices[0].message.content` | 提取 LLM 的回复文本 |
| `asyncio.run(main())` | 运行异步主函数（Python 入口标准写法） |

---

## 二、概念速查卡

### 类型注解（Type Hints）

```python
# 基本类型
name: str = "hello"        # 字符串
count: int = 42            # 整数
price: float = 9.99        # 浮点
active: bool = True        # 布尔

# 联合类型（Python 3.10+）
value: str | None = None   # 可以是 str，也可以是 None

# 函数注解
def greet(name: str) -> str:    # 参数类型 → 返回值类型
    return f"Hello, {name}"

# 集合类型（Python 3.9+）
items: list[str] = ["a", "b"]         # 字符串列表
scores: dict[str, int] = {"math": 90} # 键是 str，值是 int
```

### @dataclass vs 普通类

```python
# ❌ 普通类——写很多样板代码
class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

# ✅ dataclass——自动生成 __init__/__repr__/__eq__
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(1, 2)
print(p)  # Point(x=1, y=2)  ← 自动有可读的打印
```

---

## 三、动手练习（15-20 分钟）

在 `ai-foundation/examples/` 下新建 `my_typing_practice.py`，完成以下三个任务：

### 任务 1：写一个带类型注解的函数

```python
def count_tokens(text: str) -> int:
    """估算文本的 token 数（中文约 1 个字符 = 1 token，粗暴按 1/3 折算）。"""
    return len(text) // 3
```

然后测试它：
```python
print(count_tokens("你好世界"))        # 预期：1
print(count_tokens("Hello World"))     # 预期：3
```

### 任务 2：写一个 dataclass

```python
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    data: str
    error: str | None = None  # 默认 None，成功时不需要填
```

然后测试它：
```python
ok = ToolResult(success=True, data="操作成功")
fail = ToolResult(success=False, data="", error="连接超时")
print(ok)
print(fail)
```

### 任务 3：用 load_dotenv 读 .env

```python
from dotenv import load_dotenv
import os

load_dotenv()  # 把 .env 的内容加载到环境变量

api_key = os.getenv("DEEPSEEK_API_KEY", "")
if api_key:
    print(f"Key 前 8 位: {api_key[:8]}...")
else:
    print("未找到 DEEPSEEK_API_KEY")
```

---

## 四、验收标准

在 `ai-foundation/` 目录下运行：

```bash
python examples/my_typing_practice.py
```

预期输出类似：

```
1
3
ToolResult(success=True, data='操作成功', error=None)
ToolResult(success=False, data='', error='连接超时')
Key 前 8 位: sk-e712b...
```

跑通后把输出贴给我，D1 就算过了，进入 D2。

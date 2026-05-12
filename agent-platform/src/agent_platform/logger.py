"""Agent 日志系统 —— 替代 print，写文件 + 分级 + 轮转。"""

import logging
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent.parent.parent / "data"
LOG_DIR.mkdir(exist_ok=True)

_logger = None


def get_logger(name: str = "agent") -> logging.Logger:
    global _logger
    if _logger:
        return _logger

    _logger = logging.getLogger(name)
    _logger.setLevel(logging.DEBUG)

    # 文件输出 — 按天轮转
    today = datetime.now().strftime("%Y%m%d")
    fh = logging.FileHandler(LOG_DIR / f"agent-{today}.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%m-%d %H:%M:%S"
    ))
    _logger.addHandler(fh)

    # 控制台输出 — INFO 以上
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)-7s | %(message)s"))
    _logger.addHandler(ch)

    return _logger


def log_llm_call(model: str, tokens: int, ms: float):
    """记录 LLM 调用。"""
    get_logger().info(f"LLM call: model={model} tokens={tokens} latency={ms:.0f}ms")


def log_tool_call(name: str, args: dict, result_preview: str):
    """记录工具调用。"""
    get_logger().debug(f"Tool call: {name}({str(args)[:80]}) → {result_preview[:80]}")


def log_error(where: str, error: str):
    """记录错误。"""
    get_logger().error(f"{where}: {error}")


def log_agent_start(user: str, question: str):
    """Agent 开始执行。"""
    get_logger().info(f"Agent start: user={user} question={question[:80]}")


def log_agent_end(user: str, tokens: int, tools: int, ms: float):
    """Agent 执行结束。"""
    get_logger().info(f"Agent end: user={user} tokens={tokens} tools={tools} latency={ms:.0f}ms")

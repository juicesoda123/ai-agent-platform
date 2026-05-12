"""联网搜索工具 —— DDGS（零 API Key，零注册）。"""

from ddgs import DDGS


def web_search(query: str, max_results: int = 5) -> str:
    """搜索互联网，返回网页标题 + URL + 摘要。"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "没有找到相关结果。"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] {r.get('title', '?')}\n"
                f"    URL: {r.get('href', '?')}\n"
                f"    摘要: {r.get('body', '?')[:200]}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"


def web_search_news(query: str, max_results: int = 5) -> str:
    """搜索新闻，返回时效性结果（来源 + 日期）。"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        if not results:
            return "没有找到相关新闻。"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] {r.get('title', '?')}\n"
                f"    来源: {r.get('source', '?')} | {r.get('date', '?')}\n"
                f"    URL: {r.get('url', '?')}\n"
                f"    摘要: {r.get('body', '?')[:200]}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"

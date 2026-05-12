"""网页抓取工具 —— 读取搜索结果里的网页正文。"""

import requests
from bs4 import BeautifulSoup


def fetch_page(url: str, max_length: int = 3000) -> str:
    """抓取网页正文，返回纯文本。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        # 自动检测编码
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        # 去掉 script/style/nav/footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # 去多余空行
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        clean = "\n".join(lines)

        if len(clean) > max_length:
            clean = clean[:max_length] + f"\n... (截断，原文 {len(clean)} 字符)"

        return clean
    except requests.exceptions.Timeout:
        return f"请求超时: {url}"
    except requests.exceptions.ConnectionError:
        return f"无法连接: {url}。请检查网络或 VPN。"
    except Exception as e:
        return f"抓取失败: {e}"

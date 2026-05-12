"""Streamlit Cloud 入口 —— 配置路径后加载 Agent Platform UI。

Streamlit Cloud 自动执行 `streamlit run streamlit_app.py`
"""

import sys
from pathlib import Path

# 将所有源码路径加入 Python Path
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT / "agent-platform" / "src"))
sys.path.insert(0, str(_ROOT / "single-agent" / "src"))
sys.path.insert(0, str(_ROOT / "mcp-server"))
sys.path.insert(0, str(_ROOT / "rag-system" / "src"))

# 加载 UI 模块（Streamlit 会执行其中的 st.xxx 代码来渲染页面）
ui_path = _ROOT / "agent-platform" / "src" / "agent_platform" / "ui.py"
with open(ui_path, encoding="utf-8") as f:
    exec(f.read())

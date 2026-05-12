# Agent Platform Docker 镜像
# 本地构建: docker build -t agent-platform -f agent-platform/Dockerfile .
# Hugging Face: 自动检测并构建

FROM python:3.12-slim

WORKDIR /app

# Node.js (MCP 工具需要)
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY agent-platform/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY agent-platform/src/agent_platform/ ./agent_platform/
COPY single-agent/src/agent/ ./agent/
COPY mcp-server/ ./mcp-server/
COPY route/ ./route/

ENV PYTHONPATH=/app
ENV DEEPSEEK_BASE_URL=https://api.deepseek.com

EXPOSE 7860

CMD ["streamlit", "run", "agent_platform/ui.py", "--server.port", "7860", "--server.address", "0.0.0.0"]

FROM python:3.12-slim

WORKDIR /app

# Node.js for MCP tools
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY agent-platform/src/agent_platform/ ./agent_platform/
COPY single-agent/src/agent/ ./agent/
COPY mcp-server/ ./mcp-server/
COPY rag-system/src/rag_system/ ./rag_system/
COPY route/ ./route/

ENV PYTHONPATH=/app
ENV DEEPSEEK_BASE_URL=https://api.deepseek.com
ENV STREAMLIT_SERVER_PORT=7860

CMD ["streamlit", "run", "agent_platform/ui.py", "--server.port", "7860", "--server.address", "0.0.0.0"]
